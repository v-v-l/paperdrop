**status**: DONE
**title**: Internationalization for bot messages and Mini App
**agent**: backend-developer
**depends-on**: ticket-006, ticket-010
**blocks**: None

## Problem
All user-facing strings (bot messages, Mini App UI, error messages) must go through i18n. Start with English, structured for easy addition of other languages later.

## Requirements
- [ ] Create `backend/app/i18n/` module:
  - `__init__.py` -- i18n setup, JSON loader, `get_text(locale, module, key)` helper
  - `locales/en/bot.json` -- all bot message strings:
    - `bot.welcome` -- /start welcome message
    - `bot.help` -- /help text
    - `bot.processing` -- "Converting your article..." acknowledgment
    - `bot.completed` -- "Here's your EPUB!" with file
    - `bot.failed` -- "Sorry, conversion failed: {reason}"
    - `bot.rate_limited` -- "Too many requests. Try again in {minutes} minutes."
    - `bot.free_limit_reached` -- "You've used all 5 free conversions. /subscribe for unlimited."
    - `bot.invalid_url` -- "That doesn't look like a valid URL."
    - `bot.status_free` -- "Free plan: {used}/{limit} conversions used"
    - `bot.status_pro` -- "Pro plan: active until {date}"
    - `bot.payment_success` -- "Payment successful! You now have unlimited conversions."
    - `bot.privacy` -- privacy disclaimer text
    - `bot.legal` -- legal disclaimer text
  - `locales/en/miniapp.json` -- Mini App UI strings:
    - `miniapp.settings.title`, `miniapp.settings.kindle_email`, `miniapp.settings.grayscale`, `miniapp.settings.save`, `miniapp.settings.saved`
    - `miniapp.history.title`, `miniapp.history.empty`, `miniapp.history.status.*`
    - `miniapp.subscription.title`, `miniapp.subscription.free`, `miniapp.subscription.pro`, `miniapp.subscription.subscribe`
  - `locales/en/common.json` -- shared strings (errors, generic messages)
- [ ] Update bot handlers to use `get_text()` with user's `language_code` from Telegram
- [ ] Create `miniapp/i18n.js` -- simple JS i18n helper that loads locale JSON and provides `t(key)` function
- [ ] Update Mini App to use `t()` for all displayed strings
- [ ] Default to English when user's language is not available

## Scope
- `backend/app/i18n/__init__.py`
- `backend/app/i18n/locales/en/bot.json`
- `backend/app/i18n/locales/en/miniapp.json`
- `backend/app/i18n/locales/en/common.json`
- `backend/app/services/telegram/handlers.py` -- update to use i18n
- `miniapp/i18n.js` -- frontend i18n helper
- `miniapp/locales/en.json` -- frontend locale file
- `miniapp/app.js` -- update to use i18n

## Notes
- Use the user's `language_code` from Telegram user object (set on first interaction, stored in User model)
- For MVP, only English locale is needed -- but the structure must support adding locales easily
- Bot messages support Telegram markdown formatting -- i18n strings can include markdown
- Mini App serves locale JSON statically -- no API call needed
- Key format follows CLAUDE.md convention: `{module}.{section}.{key}`
