"""Resolve readable result paths from verified competition metadata."""

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class StorageConflict(ValueError):
    """No safe, unambiguous final destination exists."""


def slug(value):
    text = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def race_id(url):
    parts = urlsplit(url)
    match = re.search(r"/(?:races?|competitions?)/(\d+)(?:/|$)", parts.path)
    if match:
        return match[1]
    for key in ("race_id", "competition_id", "id"):
        values = parse_qs(parts.query).get(key, [])
        if len(values) == 1 and re.fullmatch(r"[a-zA-Z0-9]+", values[0]):
            return values[0].lower()
    return None


def url_key(url):
    parts = urlsplit(url)
    return (
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path.rstrip("/"),
        parts.query,
    )


def race_date(document):
    value = document["competition"].get("date")
    try:
        if not value or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError()
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise StorageConflict(
            "Competition date is unknown/invalid; retain pending JSON outside final data"
        ) from None


def readable_name(document):
    competition = document["competition"]
    year = race_date(document).year
    name = slug(competition.get("name"))
    place = slug(competition.get("place"))
    # Date already identifies the edition/round; retain the official name in JSON.
    name = re.sub(rf"\b{year}\b", "", name)
    name = re.sub(r"\b\d+-(?:finalove-)?kolo\b", "", name)
    name = re.sub(r"-+", "-", name).strip("-")
    if not name:
        raise StorageConflict("Competition name is unknown; no safe readable filename")
    if place:
        # Remove repeated whole place phrases before appending exactly once.
        name = re.sub(rf"(?:^|-){re.escape(place)}(?=-|$)", "-", name)
        name = re.sub(r"-+", "-", name).strip("-")
        name = f"{name}-{place}" if name else place
    return name


def read_existing(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("competition"), dict):
            raise ValueError("missing competition object")
        return data
    except (OSError, ValueError) as exc:
        raise StorageConflict(f"Cannot inspect existing result {path}: {exc}") from exc


def same_event(left, right):
    a, b = left["competition"], right["competition"]

    def event_name(competition):
        name = slug(competition.get("name"))
        place = slug(competition.get("place"))
        if place:
            name = re.sub(rf"(?:^|-){re.escape(place)}(?=-|$)", "-", name)
        return re.sub(r"-+", "-", name).strip("-")

    return (
        a.get("date") == b.get("date")
        and bool(event_name(a))
        and event_name(a) == event_name(b)
        and slug(a.get("place")) == slug(b.get("place"))
    )


def resolve_path(document, data_root):
    """No mutations. Source identity takes priority over generated names."""
    root = Path(data_root)
    if root.name == "results":
        raise StorageConflict("data/results is forbidden; pass the data root instead")
    when = race_date(document)
    base = readable_name(document)
    year = root / str(when.year)
    files = sorted(root.glob("[0-9][0-9][0-9][0-9]/*/*.json"))
    inventory = []
    for path in files:
        try:
            inventory.append((path, read_existing(path)))
        except StorageConflict:
            # An unrelated historical year cannot determine this year's destination.
            if path.parent.parent == year:
                raise
    source = document["source_file"]
    existing = [
        p
        for p, d in inventory
        if d.get("source_file") and url_key(d["source_file"]) == url_key(source)
    ]
    if len(existing) > 1:
        raise StorageConflict(f"Multiple files for the same source: {existing}")
    if existing:
        path = existing[0]
        if path.parent.parent != year:
            raise StorageConflict(
                f"Source already exists in a different competition year: {path}"
            )
        return path
    matches = {
        p.parent
        for p, d in inventory
        if p.parent.parent == year and same_event(document, d)
    }
    if len(matches) > 1:
        raise StorageConflict(f"Ambiguous competition folders: {sorted(matches)}")
    if matches:
        folder = next(iter(matches))
        # Different explicit race IDs may share otherwise identical display metadata.
        for p, d in inventory:
            if p.parent == folder and same_event(document, d):
                other_id = race_id(d.get("source_file", ""))
                if not (race_id(source) and other_id and race_id(source) != other_id):
                    raise StorageConflict(
                        f"Existing result may represent the same competition: {p}"
                    )
    else:
        # Empty custom folders can be matched only with BOTH event and place evidence.
        empty_matches, weak_matches = [], []
        place = slug(document["competition"].get("place"))
        event = set(base.split("-")) - set(place.split("-")) - {"cup", "pohar"}
        occupied = {p.parent for p, d in inventory}
        if year.exists():
            for candidate in sorted(year.iterdir()):
                if not candidate.is_dir() or candidate in occupied:
                    continue
                label = slug(candidate.name)
                tokens = set(label.split("-"))
                if place and set(place.split("-")) <= tokens:
                    candidate_event = (
                        tokens
                        - set(place.split("-"))
                        - {"cup", "pohar", str(when.year)}
                    )
                    if event and event == candidate_event:
                        empty_matches.append(candidate)
                    elif label == place:
                        weak_matches.append(candidate)
                elif event and tokens - {"cup", "pohar", str(when.year)} == event:
                    weak_matches.append(candidate)
        if len(empty_matches) > 1 or (not empty_matches and weak_matches):
            raise StorageConflict(
                f"Ambiguous empty competition folders: {empty_matches or weak_matches}"
            )
        folder = empty_matches[0] if empty_matches else year / base
        if folder.exists() and folder in occupied:
            # Same generated folder name, but its documents identify another event.
            identifier = race_id(source)
            if not identifier:
                raise StorageConflict(
                    f"Competition folder collision without source race ID: {folder}"
                )
            folder = year / f"{base}-{identifier}"
            if folder.exists():
                raise StorageConflict(f"Competition folder collision: {folder}")
    path = folder / f"{when.isoformat()}-{base}.json"
    if path.exists():
        identifier = race_id(source)
        if not identifier:
            raise StorageConflict(f"Filename collision without source race ID: {path}")
        path = folder / f"{when.isoformat()}-{base}-{identifier}.json"
        if path.exists():
            raise StorageConflict(f"Filename collision: {path}")
    return path
