from typing import List, Optional, Dict, Any
from bson import ObjectId
from app.db.database import db
from app.models.competition import CompetitionInDB, CompetitionDetail, CompetitionCategorySummary, CompetitionsPage
from app.models.result import ResultInDB
import re
from datetime import datetime, timedelta

competitions_collection = db["competitions"]
categories_collection = db["categories"]
results_collection = db["results"]
athletes_collection = db["athletes"]

async def get_competition_detail_service(competition_id: str) -> CompetitionDetail:
	"""Vrátí detail soutěže jako CompetitionDetail."""
	try:
		comp_oid = ObjectId(competition_id)
	except Exception:
		raise ValueError("Invalid competition id")
	
	comp = await competitions_collection.find_one({"_id": comp_oid})
	if not comp:
		raise ValueError("Competition not found")

	# Fetch all results for this competition
	all_results = await results_collection.find({"competition": comp_oid}).to_list(length=None)
	
	# Group results by category
	categories_dict = {}
	for result in all_results:
		cat_oid = result.get("category")
		if cat_oid:
			category_id_str = str(cat_oid)
			if category_id_str not in categories_dict:
				categories_dict[category_id_str] = []
			categories_dict[category_id_str].append(result)
	
	# Build category summaries
	categories_summaries = []
	total_athlete_count = 0
	
	for category_id_str, results_in_cat in categories_dict.items():
		# Get category details
		cat_oid = ObjectId(category_id_str)
		cat = await categories_collection.find_one({"_id": cat_oid})
		if cat:
			competitor_count = len(results_in_cat)
			total_athlete_count += competitor_count
			categories_summaries.append(
				CompetitionCategorySummary(
					id=category_id_str,
					name=cat.get("name", ""),
					competitors_count=competitor_count,
				)
			)

	return CompetitionDetail(
		id=str(comp["_id"]),
		name=comp.get("name"),
		place=comp.get("place"),
		date=comp.get("date"),
		league=comp.get("league"),
		athlete_count=total_athlete_count,
		categories=categories_summaries,
	)

async def get_competitions_service(
	search: Optional[str] = None,
	page: int = 1,
	page_size: int = 25,
	sort_key: str = "date",
	sort_dir: str = "desc",
) -> CompetitionsPage:
	"""Vrátí stránkovaný seznam soutěží s volitelným vyhledáváním."""
	query: Dict[str, Any] = {}
	if search and search.strip():
		raw = search.strip()
		# Zachovej data (2024-01-15, 15.01.2024) jako celek
		tokens = re.findall(r'\d{1,2}\.\d{1,2}\.\d{4}|\d{4}[-/.]\d{2}[-/.]\d{2}|\S+', raw)

		def _token_conditions(token: str) -> dict:
			"""Vytvoří OR podmínky pro jeden token, včetně rozpoznání roku a data."""
			or_cond: list = [
				{"name": {"$regex": token, "$options": "i"}},
				{"place": {"$regex": token, "$options": "i"}},
				{"league": {"$regex": token, "$options": "i"}},
			]
			# 4ciferný rok → hledat i v date rozsahu celého roku
			if re.fullmatch(r'\d{4}', token):
				year = int(token)
				or_cond.append({
					"date": {
						"$gte": datetime(year, 1, 1),
						"$lt": datetime(year + 1, 1, 1),
					}
				})
			else:
				# Zkus parsovat celé datum (6.9.2025, 06.09.2025, 2025-09-06 apod.)
				parsed_date = None
				for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d"):
					try:
						parsed_date = datetime.strptime(token, fmt)
						break
					except ValueError:
						continue
				if parsed_date:
					day_start = datetime(parsed_date.year, parsed_date.month, parsed_date.day)
					day_end = day_start + timedelta(days=1)
					or_cond.append({
						"date": {"$gte": day_start, "$lt": day_end}
					})
			return {"$or": or_cond}

		if len(tokens) > 1:
			query["$and"] = [_token_conditions(t) for t in tokens]
		else:
			query.update(_token_conditions(tokens[0]))

	# Řazení
	allowed_sort_keys = {"date", "name", "place"}
	sk = sort_key if sort_key in allowed_sort_keys else "date"
	sd = -1 if sort_dir == "desc" else 1

	total = await competitions_collection.count_documents(query)
	skip = (page - 1) * page_size

	competitions_raw = (
		await competitions_collection.find(query)
		.collation({"locale": "cs", "strength": 1})
		.sort(sk, sd)
		.skip(skip)
		.limit(page_size)
		.to_list(length=page_size)
	)

	result = []
	for comp in competitions_raw:
		comp["_id"] = str(comp["_id"])
		result.append(CompetitionInDB.model_validate(comp))

	return CompetitionsPage(
		items=result,
		total=total,
		page=page,
		page_size=page_size,
	)

async def get_results_for_category_service(competition_id: str, category_id: str) -> List[ResultInDB]:
	"""Vrátí výsledky pro danou soutěž a kategorii jako seznam ResultInDB."""

	try:
		comp_oid = ObjectId(competition_id)
		cat_oid = ObjectId(category_id)
	except Exception:
		raise ValueError("Invalid competition_id or category_id")
	
	results_raw = await results_collection.find({"competition": comp_oid, "category": cat_oid}).to_list(length=None)

	# Helper function to resolve and embed reference
	async def resolve_ref(collection, ref_id_str):
		try:
			oid = ObjectId(ref_id_str)
			doc = await collection.find_one({"_id": oid})
			if not doc:
				raise ValueError(f"Referenced doc not found: {ref_id_str}")
			doc["_id"] = str(doc["_id"])
			return doc
		except Exception:
			raise ValueError(f"Invalid reference id: {ref_id_str}")

	result = []
	for r in results_raw:
		out = dict(r)
		out["_id"] = str(out["_id"])

		# Resolve and embed references
		if r.get("athlete"):
			out["athlete"] = await resolve_ref(athletes_collection, str(r["athlete"]))

		if r.get("competition"):
			comp = await resolve_ref(competitions_collection, str(r["competition"]))
			# Normalize categories to strings
			if isinstance(comp.get("categories"), list):
				comp["categories"] = [str(x) for x in comp["categories"]]
			out["competition"] = comp

		if r.get("category"):
			out["category"] = await resolve_ref(categories_collection, str(r["category"]))

		result.append(ResultInDB.model_validate(out))

	return result