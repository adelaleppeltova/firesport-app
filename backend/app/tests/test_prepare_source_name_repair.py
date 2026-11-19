from copy import deepcopy

from bson import ObjectId, decode_all

from scripts.migrate_category_catalog import fingerprint
from scripts.prepare_source_name_repair import prepare, write_bundle


def test_prepare_limits_fields_and_backs_up_only_unchanged_rows(tmp_path):
    ids = [ObjectId() for _ in range(4)]
    rows = {identifier: {"_id": identifier, "imported_athlete": {"first_name": "", "last_name": ""},
                         "classification_status": "active", "rank": 2} for identifier in ids}
    updates = [{"id": key, "document_sha256": fingerprint(row),
                "set": {"source_full_name": "Novák Jan Pavel", "source_name_evidence": {"kind": "html"},
                        "match_status": "needs_review", "match_reason": "name_segmentation_review"}}
               for key, row in rows.items()]
    original = {"updates": updates}
    replay = deepcopy(original)
    rows[ids[1]]["imported_athlete"]["first_name"] = "Jan"
    rows[ids[2]]["rank"] = 3
    replay["updates"][3]["set"]["source_full_name"] = "Jiný Výsledek"

    report, backup = prepare({"results": rows}, original, replay)
    assert [row["id"] for row in report["updates"]] == ids[:1]
    assert set(report["updates"][0]["set"]) == {"source_full_name", "source_name_evidence"}
    assert [row["reason"] for row in report["conflicts"]] == [
        "already_edited_or_linked", "document_changed", "source_changed_or_expanded_repair",
    ]
    write_bundle(tmp_path / "bundle", report, backup)
    assert decode_all((tmp_path / "bundle" / "results-before.bson").read_bytes()) == [rows[ids[0]]]
