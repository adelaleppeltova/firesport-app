
from fastapi import APIRouter, Depends
from app.db.database import get_db
from fastapi import HTTPException
from typing import List
from bson import ObjectId

router = APIRouter(prefix="/competitions", tags=["competitions"])

@router.get("/{id}/detail")
async def get_competition_detail(id: str, db=Depends(get_db)):
    comp = await db["competitions"].find_one({"_id": ObjectId(id)})
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")
    # Převod všech ObjectId na string (pro jsonable_encoder)
    for k, v in comp.items():
        if isinstance(v, ObjectId):
            comp[k] = str(v)

    # Získání kategorií (pole může obsahovat ObjectId nebo dicty)
    categories = comp.get("categories", [])
    category_objs = []
    for cat in categories:
        if isinstance(cat, ObjectId) or (isinstance(cat, str) and len(cat) == 24):
            # Načti kategorii z kolekce categories
            cat_id = str(cat)
            cat_doc = await db["categories"].find_one({"_id": ObjectId(cat_id)})
            if cat_doc:
                category_objs.append({"_id": cat_id, "name": cat_doc.get("category_name", cat_id)})
            else:
                category_objs.append({"_id": cat_id, "name": cat_id})
        elif isinstance(cat, dict):
            # Pokud už je dict s názvem
            cat_id = str(cat.get("_id"))
            name = cat.get("category_name", cat_id)
            category_objs.append({"_id": cat_id, "name": name})
        else:
            # fallback
            category_objs.append({"_id": str(cat), "name": str(cat)})

    # Pokud nejsou v competition, zkus z results
    if not category_objs:
        result_cats = await db["results"].find({"competition_id": id}).to_list(length=None)
        cat_ids = list({r.get("category") for r in result_cats if r.get("category")})
        for cat_id in cat_ids:
            cat_doc = await db["categories"].find_one({"_id": ObjectId(cat_id)})
            if cat_doc:
                category_objs.append({"_id": str(cat_id), "name": cat_doc.get("category_name", str(cat_id))})
            else:
                category_objs.append({"_id": str(cat_id), "name": str(cat_id)})

    # Počet unikátních závodníků podle results
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
