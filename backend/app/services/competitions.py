from typing import List
from bson import ObjectId
from app.db.database import db
from app.models.competition import CompetitionInDB
from app.models.result import ResultInDB

competitions_collection = db["competitions"]
categories_collection = db["categories"]
results_collection = db["results"]
athletes_collection = db["athletes"]

async def get_competition_detail_service(id: str) -> CompetitionInDB:
	"""Vrátí detail soutěže jako CompetitionInDB."""
	try:
		comp_oid = ObjectId(id)
	except Exception:
		raise ValueError("Invalid competition id")
	
	comp = await competitions_collection.find_one({"_id": comp_oid})
	if not comp:
		raise ValueError("Competition not found")
	
	return CompetitionInDB.model_validate(comp)

async def get_competitions_service() -> List[CompetitionInDB]:
	"""Vrátí seznam všech soutěží."""
	competitions_raw = await competitions_collection.find({}).to_list(length=None)
	return [CompetitionInDB.model_validate(c) for c in competitions_raw]

async def get_results_for_category_service(competition_id: str, category_id: str) -> List[ResultInDB]:
	"""Vrátí výsledky pro danou soutěž a kategorii jako seznam ResultInDB."""

	try:
		comp_oid = ObjectId(competition_id)
		cat_oid = ObjectId(category_id)
	except Exception:
		raise ValueError("Invalid competition_id or category_id")
	
	results_raw = await results_collection.find({"competition_id": comp_oid, "category_id": cat_oid}).to_list(length=None)

	return [ResultInDB.model_validate(r) for r in results_raw]