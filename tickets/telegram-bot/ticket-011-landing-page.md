**title**: Static landing page with value proposition and bot link
**agent**: frontend-developer
**depends-on**: ticket-001
**blocks**: None

## Problem
We need a simple public landing page that explains what the bot does, how it works, pricing, and links to the Telegram bot. Also hosts legal pages (privacy policy, terms of service).

## Requirements
- [ ] Create `landing/index.html` -- single-page landing:
  - Hero section: headline ("Turn any article into a Kindle-ready EPUB"), subheadline explaining the value (keeps images, unlike Kindle's built-in browser)
  - How it works: 3 steps (1. Open bot, 2. Send URL, 3. Get EPUB)
  - Pricing: Free tier (5 conversions) + Pro ($4.99/month unlimited)
  - CTA button: "Open in Telegram" linking to `https://t.me/BOT_USERNAME`
  - Privacy highlights: "No EPUB files stored. Only conversion metadata kept."
  - Footer: links to privacy policy, terms of service, contact
- [ ] Create `landing/privacy.html` -- privacy policy:
  - What data we collect (Telegram user ID, conversion metadata)
  - What we DON'T store (EPUB files, article content)
  - How payments are processed (via Telegram/Stripe)
  - Data retention policy
  - GDPR compliance note
- [ ] Create `landing/terms.html` -- terms of service:
  - Service description
  - "For personal reading only" disclaimer
  - Content belongs to original authors
  - No guarantee of conversion quality
  - Right to terminate accounts for abuse
- [ ] Styling:
  - Clean, modern, mobile-responsive
  - Vanilla CSS (no framework needed for 3 static pages)
  - Light/dark mode support via `prefers-color-scheme`
- [ ] SEO basics: proper meta tags, Open Graph tags, favicon

## Scope
- `landing/index.html` -- main landing page
- `landing/privacy.html` -- privacy policy
- `landing/terms.html` -- terms of service
- `landing/style.css` -- shared styles
- `landing/favicon.ico` -- simple favicon (can be placeholder)

## Notes
- The landing page is hosted separately from the bot backend (could be on Vercel, Netlify, or just nginx)
- Keep it extremely simple -- no JavaScript required (maybe minimal JS for smooth scrolling)
- The BOT_USERNAME is a placeholder -- will be configured when the bot is registered with @BotFather
- All text should be in English for now. i18n can be added later if needed.
- The legal pages should be thorough but readable. Use plain language, not dense legalese.
- Consider adding a "How it's different from Send to Kindle" comparison section
