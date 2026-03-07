**title**: Database schema and migrations for Telegram bot users, conversions, and subscriptions
**status**: DONE
**agent**: database-architect
**depends-on**: ticket-001
**blocks**: ticket-005, ticket-006, ticket-007, ticket-008, ticket-009

## Problem
We need a database schema to track Telegram users, their conversions, subscription status, and usage limits. Identity comes from Telegram (no email/password auth).

## Requirements
- [x] Create SQLAlchemy async models in `backend/app/models/`:
  - `user.py` -- `User` model
  - `conversion.py` -- `Conversion` model
  - `subscription.py` -- `Subscription` model
- [x] `User` model fields:
  - `id` (BigInteger, primary key -- Telegram user ID, NOT auto-increment)
  - `username` (String, nullable -- Telegram username)
  - `first_name` (String, nullable)
  - `language_code` (String(10), nullable -- from Telegram user object)
  - `kindle_email` (String, nullable -- user's @kindle.com address)
  - `grayscale_images` (Boolean, default True -- image preference)
  - `total_conversions` (Integer, default 0 -- denormalized counter for quick free-tier check)
  - `created_at` (DateTime with timezone)
  - `updated_at` (DateTime with timezone)
- [x] `Conversion` model fields:
  - `id` (UUID, primary key, server_default=gen_random_uuid())
  - `user_id` (BigInteger, FK to User.id, indexed)
  - `url` (Text, not null)
  - `title` (String, nullable)
  - `author` (String, nullable)
  - `status` (String -- enum: `pending`, `processing`, `completed`, `failed`)
  - `error_message` (Text, nullable)
  - `file_size_bytes` (Integer, nullable)
  - `image_count` (Integer, nullable)
  - `used_playwright` (Boolean, default False)
  - `created_at` (DateTime with timezone)
  - `completed_at` (DateTime with timezone, nullable)
- [x] `Subscription` model fields:
  - `id` (UUID, primary key)
  - `user_id` (BigInteger, FK to User.id, unique -- one active sub per user)
  - `telegram_payment_charge_id` (String, nullable -- Telegram payment ID)
  - `provider_payment_charge_id` (String, nullable -- Stripe charge ID)
  - `status` (String -- enum: `active`, `cancelled`, `expired`)
  - `current_period_start` (DateTime with timezone)
  - `current_period_end` (DateTime with timezone)
  - `created_at` (DateTime with timezone)
- [x] Initialize Alembic with async support: `backend/migrations/`
- [x] Create initial migration with all three tables
- [x] Add indexes: `conversion(user_id, created_at)`, `subscription(user_id, status)`
- [x] Create `backend/app/models/__init__.py` that imports all models (for Alembic auto-detect)

## Scope
- `backend/app/models/user.py`
- `backend/app/models/conversion.py`
- `backend/app/models/subscription.py`
- `backend/app/models/__init__.py`
- `backend/app/core/database.py` -- async engine, session factory
- `backend/migrations/` -- Alembic config + initial migration
- `backend/alembic.ini`

## Notes
- User.id is the Telegram user ID (BigInteger), NOT auto-increment. Telegram user IDs are large integers.
- `total_conversions` is denormalized for fast free-tier checks. Increment atomically on successful conversion.
- Conversion records do NOT store EPUB file data -- files are temporary. Only metadata is persisted.
- Use `datetime.timezone.utc` for all timestamps (server_default=func.now())
- The `status` fields should use Python enums mapped to String columns (not PostgreSQL native enums, for easier migration)
