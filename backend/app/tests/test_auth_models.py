import pytest
from pydantic import ValidationError

from app.models.auth import ForgotPasswordRequest, ResetPasswordRequest
from app.models.user import UserLoginRequest, UserRegisterRequest


def test_register_request_accepts_sha256_password_hash():
    payload = UserRegisterRequest(
        email="user@example.com",
        password_hash="a" * 64,
    )

    assert payload.password_hash == "a" * 64


@pytest.mark.parametrize("invalid_hash", ["short", "g" * 64, "A" * 64])
def test_register_request_rejects_invalid_password_hash_format(invalid_hash):
    with pytest.raises(ValidationError):
        UserRegisterRequest(
            email="user@example.com",
            password_hash=invalid_hash,
        )


def test_login_request_requires_client_password_hash():
    payload = UserLoginRequest(
        email="user@example.com",
        password_hash="b" * 64,
    )

    assert payload.password_hash == "b" * 64


def test_forgot_password_request_accepts_email():
    payload = ForgotPasswordRequest(email="user@example.com")

    assert payload.email == "user@example.com"


def test_reset_password_request_accepts_token_and_hash():
    payload = ResetPasswordRequest(
        token="token-value",
        password_hash="c" * 64,
    )

    assert payload.token == "token-value"


def test_reset_password_request_rejects_invalid_hash():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(
            token="token-value",
            password_hash="invalid",
        )
