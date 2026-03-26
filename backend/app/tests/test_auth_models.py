import pytest
from pydantic import ValidationError

from app.models.user import UserLoginRequest, UserRegisterRequest


def test_register_request_accepts_sha256_password_hash():
    payload = UserRegisterRequest(
        email="user@example.com",
        password_hash="a" * 64,
    )

    assert payload.password_hash == "a" * 64


@pytest.mark.parametrize(
    "invalid_hash",
    [
        "short",
        "g" * 64,
        "A" * 64,
    ],
)
def test_register_request_rejects_invalid_password_hash_format(invalid_hash):
    with pytest.raises(ValidationError):
        UserRegisterRequest(
            email="user@example.com",
            password_hash=invalid_hash,
        )


def test_login_request_allows_legacy_plaintext_password_for_migration():
    payload = UserLoginRequest(
        email="user@example.com",
        password_hash="b" * 64,
        password="Password1",
    )

    assert payload.password == "Password1"
