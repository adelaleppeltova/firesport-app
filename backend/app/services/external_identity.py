import json
from hashlib import sha256
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.db.database import db

external_identities = db["verified_athlete_external_ids"]


class ExternalIdentity(BaseModel):
    provider: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9.-]{0,62}$")]
    person_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")]
    evidence_url: Annotated[str, StringConstraints(max_length=2048)]

    @field_validator("evidence_url")
    @classmethod
    def check_evidence_url(cls, value: str) -> str:
        url = urlsplit(value)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError("Expected a public source URL")
        return value

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.person_id}"


def payload_digest(data: dict) -> str:
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


class ExternalIdentitySidecar(BaseModel):
    """Trusted source observations, tied to a specific immutable import payload."""

    payload_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    categories: dict[int, dict[int, ExternalIdentity]] = Field(default_factory=dict)

    def validate_for(self, data: dict, categories: list[dict]) -> None:
        if self.payload_sha256 != payload_digest(data):
            raise ValueError("Externí identifikátory patří k jinému importnímu souboru.")
        for category_index, observations in self.categories.items():
            if category_index not in range(len(categories)):
                raise ValueError("Neplatná kategorie externí identity.")
            if any(index not in range(len(categories[category_index].get("results", []))) for index in observations):
                raise ValueError("Neplatný řádek externí identity.")
