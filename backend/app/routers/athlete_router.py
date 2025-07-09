from fastapi import APIRouter
from app.models.athlete import Athlete
from app.db.database import db


router = APIRouter(prefix="/athletes", tags=["athletes"])

collection = db["athletes"]

@router.post("/")
def create_athlete(athlete: Athlete):
    result = collection.insert_one(athlete.dict())
    return {"id": str(result.inserted_id)}

@router.get("/")
def list_athletes():
    athletes = list(collection.find())
    for a in athletes:
        a["_id"] = str(a["_id"])
    return athletes
