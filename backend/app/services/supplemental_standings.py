from collections import defaultdict

from bson import ObjectId

from app.category_catalog import BY_ID
from app.db.database import db
from app.models.standings import HistoricalStanding, PublishedRun, PublishedTeam, SupplementalStandings
from app.services.category_normalization import source_performance_issue
from app.services.published_standings import HISTORICAL, TEAM_MEMBER


def standalone_filters(*, discipline=None) -> dict:
    statuses = []
    if discipline in (None, "100m"):
        statuses.append(TEAM_MEMBER)
    if discipline in (None, "60m"):
        statuses.append(HISTORICAL)
    return {"classification_status": {"$in": statuses}, "duplicate_of": None}


def published_run(row: dict) -> PublishedRun:
    person = row.get("imported_athlete") or {}
    bib = row.get("start_number")
    unverified = row.get("classification_status") == HISTORICAL and bool(source_performance_issue(row))
    return PublishedRun(
        id=str(row["_id"]), rank=row.get("rank"),
        start_number=str(bib) if bib is not None else None,
        published_name=row.get("published_name") or (
            row.get("source_full_name") if not (person.get("first_name") and person.get("last_name")) else None
        ),
        first_name=person.get("first_name") or None, last_name=person.get("last_name") or None,
        team=row.get("imported_team") or row.get("team"), times=row.get("published_attempts") or row.get("times") or [],
        final_time=None if unverified else row.get("final_time"),
        final_time_status="missing" if unverified else row.get("final_time_status", "missing"),
        final_time_unverified=unverified,
    )


def official_order(row: dict):
    rank = row.get("rank")
    return (rank is None, rank if rank is not None else 0, str(row["_id"]))


def compose_standings(competition: dict, rows: list[dict]) -> SupplementalStandings:
    by_team = defaultdict(list)
    historical_groups = defaultdict(list)
    for row in sorted(rows, key=official_order):
        if row.get("competition") != competition["_id"] or row.get("duplicate_of") is not None:
            continue
        if (row["classification_status"] == TEAM_MEMBER and row.get("result_type") == TEAM_MEMBER
                and row.get("discipline") == "100m"):
            by_team[(row.get("team_entry_id"), row.get("category"))].append(published_run(row))
        if row["classification_status"] == HISTORICAL and row.get("category") is None and row.get("discipline") == "60m":
            source = row["source_category"]
            historical_groups[(
                source.get("legacy_category_id"), row.get("result_list_id"), source["name"],
                tuple(row["historical_age_range"]), source.get("source_url"),
            )].append(published_run(row))

    teams = []
    for team in sorted(competition.get("team_results") or [], key=official_order):
        category = BY_ID.get(team["category"])
        if category is None or category.type != "team":
            continue
        teams.append(PublishedTeam(
            id=str(team["_id"]), category_id=str(category.id), category_name=category.name,
            name=team["name"], source_number=team["source_number"], rank=team["rank"],
            total_time=team["total_time"], total_status=team["total_status"], source_url=team["source_url"],
            members=by_team[team["_id"], category.id],
        ))
    groups = [
        HistoricalStanding(name=name, min_age=ages[0], max_age=ages[1], source_url=url,
                           result_list_id=block, results=results)
        for (_, block, name, ages, url), results in historical_groups.items()
    ]
    return SupplementalStandings(teams=teams, historical=sorted(groups, key=lambda group: group.name.casefold()))


async def get_supplemental_standings(competition_id: str) -> SupplementalStandings:
    if not ObjectId.is_valid(competition_id):
        raise ValueError("Invalid competition id")
    identifier = ObjectId(competition_id)
    competition = await db["competitions"].find_one({"_id": identifier}, {"team_results": 1})
    if competition is None:
        raise ValueError("Competition not found")
    rows = await db["results"].find({"competition": identifier, **standalone_filters()}).to_list(None)
    return compose_standings(competition, rows)
