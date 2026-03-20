"""Simple selectors over loaded JSON records."""

from __future__ import annotations

from typing import Any


def get_competitions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return competition-level records with source metadata."""
    competitions: list[dict[str, Any]] = []

    for record in records:
        competition = record.get("competition") or {}
        competitions.append(
            {
                "source_file": record.get("source_file"),
                "generated_at": record.get("generated_at"),
                "competition_name": competition.get("name"),
                "competition_place": competition.get("place"),
                "competition_date": competition.get("date"),
                "competition_league": competition.get("league"),
                "category_count": len(competition.get("categories") or []),
            }
        )

    return competitions


def get_categories(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return category rows enriched with competition context."""
    categories: list[dict[str, Any]] = []

    for record in records:
        competition = record.get("competition") or {}

        for category in competition.get("categories") or []:
            categories.append(
                {
                    "source_file": record.get("source_file"),
                    "competition_name": competition.get("name"),
                    "competition_place": competition.get("place"),
                    "competition_date": competition.get("date"),
                    "competition_league": competition.get("league"),
                    "category_name": category.get("name"),
                    "discipline": category.get("discipline"),
                    "result_count": len(category.get("results") or []),
                }
            )

    return categories


def get_results(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return flattened result rows with competition and category context."""
    results: list[dict[str, Any]] = []

    for record in records:
        competition = record.get("competition") or {}

        for category in competition.get("categories") or []:
            for result in category.get("results") or []:
                results.append(
                    {
                        "source_file": record.get("source_file"),
                        "competition_name": competition.get("name"),
                        "competition_place": competition.get("place"),
                        "competition_date": competition.get("date"),
                        "competition_league": competition.get("league"),
                        "category_name": category.get("name"),
                        "discipline": category.get("discipline"),
                        "start_number": result.get("start_number"),
                        "fscode": result.get("fscode"),
                        "first_name": result.get("first_name"),
                        "last_name": result.get("last_name"),
                        "birth_year": result.get("birth_year"),
                        "team": result.get("team"),
                        "district": result.get("district"),
                        "times": result.get("times"),
                        "final_time": result.get("final_time"),
                        "final_status": result.get("final_status"),
                        "rank": result.get("rank"),
                    }
                )

    return results


def filter_results_by_discipline(
    results: list[dict[str, Any]], discipline: str
) -> list[dict[str, Any]]:
    """Return only results for the selected discipline."""
    return [result for result in results if result.get("discipline") == discipline]
