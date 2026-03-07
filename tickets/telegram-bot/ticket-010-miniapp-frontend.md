**title**: Telegram Mini App frontend (settings, history, subscription)
**agent**: frontend-developer
**depends-on**: ticket-009
**blocks**: None

## Problem
Users need a way to manage settings (Kindle email), view conversion history, and check subscription status. This is a Telegram Mini App -- a lightweight web app that runs inside Telegram's webview.

## Requirements
- [ ] Create `miniapp/index.html` -- single-page app with tab navigation:
  - **Settings tab**: Kindle email input, grayscale toggle, save button
  - **History tab**: list of past conversions (title, URL, date, status)
  - **Subscription tab**: current plan (free/pro), conversion count, subscribe/renew button
- [ ] Use Telegram WebApp JS SDK (`telegram-web-app.js`):
  - Initialize `window.Telegram.WebApp` on load
  - Get `initData` for API authentication
  - Use `Telegram.WebApp.MainButton` for primary actions
  - Use `Telegram.WebApp.BackButton` for navigation
  - Apply Telegram theme colors (`var(--tg-theme-bg-color)`, etc.)
  - Call `Telegram.WebApp.close()` when done
- [ ] Styling:
  - Use Telegram theme CSS variables for native look and feel
  - Mobile-first, responsive (Mini Apps run in mobile webview)
  - Clean, minimal UI -- settings form, scrollable history list, subscription card
  - No external CSS frameworks -- use Telegram's theme variables
- [ ] API integration:
  - On load: call `POST /api/miniapp/auth` with initData
  - Settings: GET/PUT `/api/miniapp/settings`
  - History: GET `/api/miniapp/history` with scroll-based pagination
  - Subscription: GET `/api/miniapp/subscription`
- [ ] History list items show: title (linked to original URL), date, status badge (completed/failed)
- [ ] Settings validation: Kindle email must end with `@kindle.com` or `@free.kindle.com`
- [ ] Subscription section: show "Free (X/5 used)" or "Pro (active until DATE)"
- [ ] Subscribe button: if on free tier, open Telegram payment via `Telegram.WebApp.openInvoice()` or deep link to bot /subscribe command

## Scope
- `miniapp/index.html` -- main HTML file
- `miniapp/app.js` -- application logic
- `miniapp/style.css` -- styles using Telegram theme variables
- `miniapp/manifest.json` -- Mini App manifest (if needed)

## Notes
- Telegram Mini App docs: https://core.telegram.org/bots/webapps
- The Mini App URL is set via @BotFather (`/setmenubutton` or inline keyboard with `web_app` type)
- `initData` is available immediately via `Telegram.WebApp.initData` -- send it in Authorization header
- Keep it vanilla HTML/CSS/JS -- no build step, no framework. The Mini App should be simple and fast.
- Telegram theme variables automatically match the user's Telegram theme (light/dark mode)
- Test in Telegram's webview -- desktop and mobile behave slightly differently
- File size should be minimal (<50KB total) for instant loading in Telegram
- All user-facing strings should be prepared for i18n (ticket-013) -- use a simple JS object for text constants
