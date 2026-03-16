from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user
from pydantic import BaseModel
import logging
from app.dependencies import sync_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["user"])

class PairAthleteRequest(BaseModel):
    athlete_id: str

@router.get("")
@router.get("/")
def get_me(user=Depends(get_current_user)):
    """Vrátí údaje o aktuálně přihlášeném uživateli"""
    users_collection = sync_db["users"]
    athletes_collection = sync_db["athletes"]

    athlete_id = user.get("athlete_id")
    if athlete_id:
        athlete_oid = None
        try:
            athlete_oid = ObjectId(athlete_id)
        except Exception:
            logger.warning("User %s has invalid athlete_id=%r, unsetting", user.get("id"), athlete_id)
            users_collection.update_one(
                {"_id": ObjectId(user["id"])},
                {"$unset": {"athlete_id": ""}},
            )
            athlete_id = None

        if athlete_oid is not None:
            exists = athletes_collection.find_one({"_id": athlete_oid}, {"_id": 1})
            if not exists:
                logger.warning("User %s has orphan athlete_id=%s, unsetting", user.get("id"), athlete_id)
                users_collection.update_one(
                    {"_id": ObjectId(user["id"])},
                    {"$unset": {"athlete_id": ""}},
                )
                athlete_id = None

    return {
        "user_id": user["id"],
        "email": user["email"],
        "athlete_id": athlete_id,
    }

@router.patch("/pair-athlete")
def pair_athlete(body: PairAthleteRequest, user=Depends(get_current_user)):
    """Spáruje uživatele s atletem"""
    logger.info(f"Pairing user {user['id']} with athlete {body.athlete_id}")
    
    # Použij existující sync_db z dependencies
    users_collection = sync_db["users"]
    athletes_collection = sync_db["athletes"]

    try:
        athlete_oid = ObjectId(body.athlete_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid athlete_id")

    exists = athletes_collection.find_one({"_id": athlete_oid}, {"_id": 1})
    if not exists:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    result = users_collection.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {"athlete_id": body.athlete_id}}
    )
    
    logger.info(f"Matched: {result.matched_count}, Modified: {result.modified_count}")
    
    return {"ok": True, "athlete_id": body.athlete_id}

@router.delete("/pair-athlete")
def unpair_athlete(user=Depends(get_current_user)):
    """Zruší propojení uživatele s atletem"""
    users_collection = sync_db["users"]

    result = users_collection.update_one(
        {"_id": ObjectId(user["id"])},
        {"$unset": {"athlete_id": ""}},
    )

    logger.info(
        "Unpaired user %s from athlete, matched=%s modified=%s",
        user["id"],
        result.matched_count,
        result.modified_count,
    )

    return {"ok": True, "athlete_id": None}
