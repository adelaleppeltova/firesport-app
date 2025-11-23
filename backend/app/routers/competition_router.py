
from fastapi import APIRouter, Depends
from app.db.database import get_db
from fastapi import HTTPException
from typing import List
from bson import ObjectId
from fastapi import Query


router = APIRouter(prefix="/competitions", tags=["competitions"])

@router.get("/{id}/detail")
async def get_competition_detail(id: str, db=Depends(get_db)):
    comp = await db["competitions"].find_one({"_id": ObjectId(id)})
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")
    for k, v in comp.items():
        if isinstance(v, ObjectId):
            comp[k] = str(v)

    categories = comp.get("categories", [])
    category_objs = []
    for cat in categories:
        if isinstance(cat, ObjectId) or (isinstance(cat, str) and len(cat) == 24):
            cat_id = str(cat)
            cat_doc = await db["categories"].find_one({"_id": ObjectId(cat_id)})
            if cat_doc:
                category_objs.append({"_id": cat_id, "name": cat_doc.get("category_name", cat_id)})
            else:
                category_objs.append({"_id": cat_id, "name": cat_id})
        elif isinstance(cat, dict):
            cat_id = str(cat.get("_id"))
            name = cat.get("category_name", cat_id)
            category_objs.append({"_id": cat_id, "name": name})
        else:
            category_objs.append({"_id": str(cat), "name": str(cat)})

    if not category_objs:
        result_cats = await db["results"].find({"competition_id": id}).to_list(length=None)
        cat_ids = list({r.get("category") for r in result_cats if r.get("category")})
        for cat_id in cat_ids:
            cat_doc = await db["categories"].find_one({"_id": ObjectId(cat_id)})
            if cat_doc:
                category_objs.append({"_id": str(cat_id), "name": cat_doc.get("category_name", str(cat_id))})
            else:
                category_objs.append({"_id": str(cat_id), "name": str(cat_id)})

    pipeline = [
        {"$match": {"competition_id": ObjectId(id)}},
        {"$group": {"_id": "$athlete_id"}}
    ]
    unique_athletes = await db["results"].aggregate(pipeline).to_list(length=None)
    athlete_count = len(unique_athletes)

    return {
        "_id": comp["_id"],
        "competition_name": comp.get("competition_name", "-"),
        "competition_date": comp.get("competition_date", None),
        "competition_place": comp.get("competition_place", "-"),
        "competition_type": comp.get("competition_type", "-"),
        "athlete_count": athlete_count,
        "categories": category_objs,
    }

@router.get("", response_model=List[dict])
async def get_competitions(db=Depends(get_db)):
    competitions = []
    cursor = db["competitions"].find({})
    async for comp in cursor:
        comp["_id"] = str(comp["_id"])
        competitions.append({
            "_id": comp["_id"],
            "competition_name": comp.get("competition_name", "-"),
            "competition_date": comp.get("competition_date", None),
            "competition_place": comp.get("competition_place", "-"),
        })
    return competitions


@router.get("/{competition_id}/results/{category_id}")
async def get_results_for_category(
    competition_id: str,
    category_id: str,
    db=Depends(get_db)
):
    from bson import ObjectId
    results_cursor = db["results"].find({
        "competition_id": ObjectId(competition_id),
        "category_id": ObjectId(category_id)
    })
    results = await results_cursor.to_list(length=None)
    athlete_ids = [r["athlete_id"] for r in results if "athlete_id" in r]
    athletes = {}
    if athlete_ids:
        athletes_cursor = db["athletes"].find({"_id": {"$in": athlete_ids}})
        async for athlete in athletes_cursor:
            athletes[athlete["_id"]] = athlete
    response = []
    for r in results:
        athlete = athletes.get(r.get("athlete_id"), {})
        response.append({
            "start_number": r.get("start_number"),
            "first_name": athlete.get("first_name", ""),
            "last_name": athlete.get("last_name", ""),
            "birth_year": athlete.get("birth_year", ""),
            "fscode": athlete.get("fscode", ""),
            "team": athlete.get("team", ""),
            "time_1": r.get("time_1"),
            "time_1_status": r.get("time_1_status"),
            "time_2": r.get("time_2"),
            "time_2_status": r.get("time_2_status"),
            "final_time": r.get("final_time"),
            "final_time_status": r.get("final_time_status"),
            "rank": r.get("rank"),
        })
    response.sort(key=lambda x: (x["rank"] if x["rank"] is not None else 9999))
    return response


    

