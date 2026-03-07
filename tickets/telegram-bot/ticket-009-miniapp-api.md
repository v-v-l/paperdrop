**title**: Mini App API endpoints and Telegram WebApp auth
**agent**: backend-developer
**depends-on**: ticket-002, ticket-006
**blocks**: ticket-010

## Problem
The Telegram Mini App needs API endpoints for settings management, conversion history, and subscription status. Auth is handled by validating Telegram WebApp `initData` -- no email/password needed.

## Requirements
- [ ] Create `backend/app/services/telegram/auth.py`:
  - `validate_init_data(init_data: str, bot_token: str) -> dict` -- validate Telegram WebApp initData signature
  - Parse the `initData` query string, verify HMAC-SHA256 signature using bot token
  - Extract and return user data (user_id, username, first_name, language_code)
  - Raise `HTTPException(401)` if validation fails
- [ ] Create `backend/app/api/miniapp.py` with endpoints:
  - `POST /api/miniapp/auth` -- validate initData, return user profile + subscription status + conversion count
  - `GET /api/miniapp/settings` -- get user settings (kindle_email, grayscale_images)
  - `PUT /api/miniapp/settings` -- update user settings (kindle_email, grayscale_images)
  - `GET /api/miniapp/history` -- paginated conversion history (last 50, with cursor pagination)
  - `GET /api/miniapp/subscription` -- subscription status, expiry date, conversion count vs limit
- [ ] Create Pydantic schemas in `backend/app/schemas/`:
  - `miniapp.py` -- `SettingsResponse`, `SettingsUpdate`, `ConversionHistoryItem`, `ConversionHistoryResponse`, `SubscriptionStatusResponse`, `AuthRequest`, `AuthResponse`
- [ ] Auth middleware/dependency: FastAPI dependency that extracts and validates initData from Authorization header
- [ ] Serve Mini App static files: mount `miniapp/` directory as static files at `/miniapp/`

## Scope
- `backend/app/services/telegram/auth.py` -- initData validation
- `backend/app/api/miniapp.py` -- Mini App API endpoints
- `backend/app/schemas/miniapp.py` -- request/response schemas
- `backend/app/main.py` -- mount static files, register miniapp router

## Notes
- Telegram WebApp initData validation spec: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
- The HMAC is: HMAC_SHA256(HMAC_SHA256("WebAppData", bot_token), data_check_string)
- `data_check_string` is all fields sorted alphabetically, joined with newline, excluding `hash`
- The initData is sent by the Mini App JS SDK on load -- frontend passes it in Authorization header
- Kindle email validation: must end with @kindle.com or @free.kindle.com
- History pagination: use `created_at` cursor, not offset (more efficient for append-only data)
- Static file serving: `app.mount("/miniapp", StaticFiles(directory="miniapp", html=True), name="miniapp")`
