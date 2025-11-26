from typing import List, Dict, Any
from bson import ObjectId
from app.db.database import db
from app.models.competition import CompetitionInDB
from app.models.category import CategoryInDB
from app.models.athlete import AthleteInDB
from app.models.result import ResultInDB

competitions_collection = db["competitions"]
categories_collection = db["categories"]
results_collection = db["results"]
athletes_collection = db["athletes"]

async def get_competition_detail_service(id: str) -> CompetitionInDB | None:
	comp = await competitions_collection.find_one({"_id": ObjectId(id)})
	if not comp:
		return None
	comp["_id"] = str(comp["_id"])
	if "categories" in comp:
		comp["categories"] = [str(cat) for cat in comp["categories"]]
	return CompetitionInDB(**comp)

async def get_competitions_service() -> List[CompetitionInDB]:
	competitions = []
	cursor = competitions_collection.find({})
	async for comp in cursor:
		comp["_id"] = str(comp["_id"])
		if "categories" in comp:
			comp["categories"] = [str(cat) for cat in comp["categories"]]
		competitions.append(CompetitionInDB(**comp))
	return competitions

async def get_results_for_category_service(competition_id: str, category_id: str) -> List[ResultInDB]:
	results_cursor = results_collection.find({
		"competition_id": ObjectId(competition_id),
		"category_id": ObjectId(category_id)
	})
	results = await results_cursor.to_list(length=None)
	return [ResultInDB(**{**r, "_id": str(r["_id"])}) for r in results]
