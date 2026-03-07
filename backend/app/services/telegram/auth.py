"""Telegram WebApp initData validation.

Implements HMAC-SHA256 signature verification per the Telegram WebApp spec:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
from urllib.parse import parse_qs, unquote

from fastapi import HTTPException, status
from logs_flow import create_logger

logger = create_logger(service="telegram-auth")


def validate_init_data(init_data: str, bot_token: str) -> dict:
    """Validate Telegram WebApp initData and return parsed user data.

    Args:
        init_data: The raw initData query string from Telegram WebApp.
        bot_token: The bot token used to compute the HMAC secret.

    Returns:
        Dict with user_id, username, first_name, language_code.

    Raises:
        HTTPException(401): If the signature is invalid or data is malformed.
    """
    try:
        parsed = parse_qs(init_data, keep_blank_values=True)
    except Exception:
        logger.warning("Failed to parse initData query string")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid initData format",
        )

    received_hash = parsed.get("hash", [None])[0]
    if not received_hash:
        logger.warning("initData missing hash parameter")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing hash in initData",
        )

    # Build data_check_string: all fields except hash, sorted alphabetically, joined with \n
    data_check_parts = []
    for key in sorted(parsed.keys()):
        if key == "hash":
            continue
        # parse_qs returns lists; take the first value
        value = parsed[key][0]
        data_check_parts.append(f"{key}={value}")

    data_check_string = "\n".join(data_check_parts)

    # HMAC: secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()

    # computed_hash = HMAC_SHA256(secret_key, data_check_string)
    computed_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        logger.warning("initData HMAC validation failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid initData signature",
        )

    # Extract user data from the "user" field (JSON-encoded)
    user_raw = parsed.get("user", [None])[0]
    if not user_raw:
        logger.warning("initData missing user field")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user in initData",
        )

    try:
        user_data = json.loads(unquote(user_raw))
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse user JSON from initData")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user data in initData",
        )

    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user id in initData",
        )

    return {
        "user_id": int(user_id),
        "username": user_data.get("username"),
        "first_name": user_data.get("first_name"),
        "language_code": user_data.get("language_code"),
    }
