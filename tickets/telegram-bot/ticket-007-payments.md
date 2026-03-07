**title**: Telegram Payments API integration for subscriptions (Stripe provider)
**agent**: backend-developer
**depends-on**: ticket-006
**blocks**: None

## Problem
Users who exceed the free tier (5 conversions) need a paid subscription at $4.99/month. Telegram Payments API with Stripe as provider handles the payment flow natively inside Telegram.

## Requirements
- [x] Add payment handlers to `backend/app/services/telegram/handlers.py`:
  - `/subscribe` command: send invoice via `bot.send_invoice()` with:
    - Title: "Links to EPUB Pro"
    - Description: "Unlimited article-to-EPUB conversions"
    - Payload: `sub_{user_id}_{timestamp}`
    - Provider token: from settings
    - Currency: USD
    - Price: $4.99 (499 cents)
  - `pre_checkout_query` handler: validate the payment, answer `True` to approve
  - `successful_payment` handler: create/update Subscription record in DB, set status=active, period = 30 days from now
- [x] Create `backend/app/services/payments/subscription_service.py`:
  - `async def create_subscription(db, user_id, charge_id, provider_charge_id) -> Subscription`
  - `async def check_subscription(db, user_id) -> bool` -- returns True if active and not expired
  - `async def can_convert(db, user_id) -> tuple[bool, str]` -- checks free tier OR active subscription, returns (allowed, reason)
- [x] Integrate `can_convert()` check into the URL message handler (ticket-006)
- [x] Handle subscription expiry: when checking, if `current_period_end < now`, mark as expired
- [x] For MVP: single payment = 30-day access (not auto-recurring). User re-subscribes manually.
  - Recurring billing via Telegram Payments requires more complex provider setup -- defer to later

## Scope
- `backend/app/services/telegram/handlers.py` -- add payment-related handlers
- `backend/app/services/payments/__init__.py`
- `backend/app/services/payments/subscription_service.py`

## Notes
- Telegram Payments API flow: bot sends invoice -> user pays in Telegram UI -> Telegram sends pre_checkout_query -> we approve -> Telegram sends successful_payment -> we record it
- The Stripe provider token is obtained from @BotFather when setting up payments
- For testing, use Stripe test provider token from @BotFather (test mode)
- No webhook from Stripe needed -- Telegram handles the payment flow and notifies us via bot updates
- Currency must be supported by the Stripe provider (USD is always supported)
- Keep the subscription logic simple for MVP. No proration, no refunds through the bot.
- The `/subscribe` command should show current status first: if already subscribed, show expiry date instead of invoice
