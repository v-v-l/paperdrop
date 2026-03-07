"""Tests for Telegram WebApp initData validation."""

import hashlib
import hmac
import json
from urllib.parse import quote, urlencode

import pytest
from fastapi import HTTPException

from app.services.telegram.auth import validate_init_data

BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def _build_valid_init_data(
    user_id: int = 12345,
    username: str = "testuser",
    first_name: str = "Test",
) -> str:
    """Build a properly signed initData string."""
    user_data = json.dumps({
        "id": user_id,
        "username": username,
        "first_name": first_name,
        "language_code": "en",
    })

    params = {
        "user": user_data,
        "auth_date": "1700000000",
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
    }

    # Build data_check_string: sorted key=value lines (excluding hash)
    data_check_string = "\n".join(
        f"{k}={params[k]}" for k in sorted(params.keys())
    )

    # Compute HMAC
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    params["hash"] = computed_hash
    return urlencode(params)


class TestValidateInitData:
    def test_valid_init_data(self):
        init_data = _build_valid_init_data(user_id=99999, username="alice")
        result = validate_init_data(init_data, BOT_TOKEN)

        assert result["user_id"] == 99999
        assert result["username"] == "alice"
        assert result["first_name"] == "Test"
        assert result["language_code"] == "en"

    def test_invalid_hash_raises_401(self):
        init_data = _build_valid_init_data()
        # Tamper with the hash
        init_data = init_data.replace("hash=", "hash=0000")

        with pytest.raises(HTTPException) as exc_info:
            validate_init_data(init_data, BOT_TOKEN)
        assert exc_info.value.status_code == 401

    def test_missing_hash_raises_401(self):
        user_data = json.dumps({"id": 123, "username": "bob"})
        init_data = urlencode({"user": user_data, "auth_date": "1700000000"})

        with pytest.raises(HTTPException) as exc_info:
            validate_init_data(init_data, BOT_TOKEN)
        assert exc_info.value.status_code == 401

    def test_missing_user_raises_401(self):
        """initData with valid hash but no user field."""
        params = {"auth_date": "1700000000"}
        data_check_string = "\n".join(
            f"{k}={params[k]}" for k in sorted(params.keys())
        )
        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
        ).digest()
        computed_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        params["hash"] = computed_hash
        init_data = urlencode(params)

        with pytest.raises(HTTPException) as exc_info:
            validate_init_data(init_data, BOT_TOKEN)
        assert exc_info.value.status_code == 401

    def test_wrong_bot_token_rejects(self):
        init_data = _build_valid_init_data()
        with pytest.raises(HTTPException) as exc_info:
            validate_init_data(init_data, "wrong:token")
        assert exc_info.value.status_code == 401
