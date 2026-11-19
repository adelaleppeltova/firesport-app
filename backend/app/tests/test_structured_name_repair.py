import asyncio
import json
from os import environ
from urllib.parse import urlsplit
from uuid import uuid4

from bson import ObjectId
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import pytest

from app.api.v1.admin_router import router
from app.category_catalog import BY_KEY
from app.dependencies import require_admin
from app.services import admin
from scripts.prepare_structured_name_repair import conditional_update, make_plan


def example():
    identifier = ObjectId()
    url = "https://example.test/races/12"
    row = {
        "_id": identifier, "discipline": "100m", "category": BY_KEY["100m-men"].id,
        "competition": ObjectId(), "classification_status": "active", "result_type": "individual",
        "rank": 10, "team": "Svinov", "final_time": 21.49, "final_time_status": "valid",
        "match_status": "unmatched",
        "imported_athlete": {"first_name": "", "last_name": "", "birth_year": 2010, "fscode": None},
        "source_full_name": "Souček  Stanislav Gabriel",
        "source_name_evidence": {"url": url, "locator": [10, 21.49], "kind": "html"},
    }
    audit = {"rows": [{
        "id": identifier, "source_name": row["source_full_name"], "source_url": url,
        "source_locator": [10, 21.49], "classification": "independent_source",
        "field_boundary": {"first_name": "Stanislav Gabriel", "last_name": "Souček"},
        "corroborating_sources": ["https://example.test/independent"],
    }]}
    return row, audit


def test_plan_preserves_manual_edits_and_rejects_conflicting_source():
    row, audit = example()
    db = {"results": {row["_id"]: row}}
    assert make_plan(db, audit, [])["counts"]["planned_updates"] == 1
    row["imported_athlete"]["first_name"] = "Gabriel"
    assert make_plan(db, audit, [])["review"][0]["reason"] == "already_structured_or_linked"
    row["source_name_evidence"]["locator"] = [9, 21.49]
    assert make_plan(db, audit, [])["review"][0]["reason"] == "source_conflict"


def test_isolated_mongodb_roundtrip_through_admin_api(monkeypatch):
    uri = environ.get("FIRESPORT_ISOLATED_NAME_TEST_URI")
    if not uri:
        pytest.skip("Set FIRESPORT_ISOLATED_NAME_TEST_URI to a disposable MongoDB.")
    parsed = urlsplit(uri)
    assert parsed.hostname == "127.0.0.1" and parsed.port not in (None, 27017)
    sync = MongoClient(uri, serverSelectionTimeoutMS=5000)
    motor = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    database = "structured_name_test_" + uuid4().hex
    collection = sync[database].results
    monkeypatch.setattr(admin, "results_collection", motor[database].results)
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    app.dependency_overrides[require_admin] = lambda: None
    row, audit = example()
    async def get(path):
        messages = []

        async def send(message):
            messages.append(message)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        await app({"type": "http", "method": "GET", "path": path, "raw_path": path.encode(),
                   "root_path": "", "query_string": b"", "headers": [], "scheme": "http",
                   "http_version": "1.1", "server": ("test", 80)}, receive, send)
        assert messages[0]["status"] == 200
        return json.loads(b"".join(m.get("body", b"") for m in messages[1:]))

    async def read_result():
        item, = (await get("/v1/admin/import/review"))["items"]
        return item

    async def roundtrip():
        assert (await read_result())["imported_athlete"]["first_name"] == ""
        op, = make_plan({"results": {row["_id"]: row}}, audit, [])["updates"]
        assert conditional_update(collection, row, op).modified_count == 1
        stored = collection.find_one({"_id": row["_id"]})
        expected = {**row, "imported_athlete": {**row["imported_athlete"],
                    "first_name": "Stanislav Gabriel", "last_name": "Souček"},
                    "source_name_evidence": {**row["source_name_evidence"],
                                             "segmentation": op["set"]["source_name_evidence.segmentation"]}}
        assert stored == expected
        item = await read_result()
        assert item["source_full_name"] == "Souček  Stanislav Gabriel"
        assert item["imported_athlete"] == stored["imported_athlete"]
        assert item["match_status"] == "unmatched"
        details = await get(f"/v1/admin/import/source-names/{row['_id']}")
        assert details["source_full_name"] == stored["source_full_name"]
        assert details["imported_athlete"] == stored["imported_athlete"]
        assert details["segmentation"] == stored["source_name_evidence"]["segmentation"]
        assert conditional_update(collection, row, op).matched_count == 0
        assert not make_plan({"results": {row["_id"]: stored}}, audit, [])["updates"]

    try:
        collection.insert_one(row)
        asyncio.run(roundtrip())
    finally:
        sync.drop_database(database)
        motor.close()
        sync.close()
