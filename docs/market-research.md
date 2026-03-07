# Market Research: Links to EPUB

*Date: 2026-03-06*

## Product Concept

Telegram Bot + Mini App that converts web article URLs into EPUB files with images preserved. Users send a URL, get an EPUB back in chat. Pricing: $4.99/month, first 5 conversions free.

## Key Differentiator

Amazon's own "Send to Kindle" and most third-party tools drop images from web articles. We preserve them — downloaded, optimized, and embedded directly in the EPUB.

## Addressable Market

| Metric | Value | Source |
|--------|-------|--------|
| Global Kindle market size (2025) | $18B | [Business Research Insights](https://www.businessresearchinsights.com/market-reports/amazon-kindle-market-120402) |
| Projected market size (2026) | $18.9B | Business Research Insights |
| CAGR | 4.78% | Business Research Insights |
| Amazon global e-reader share | 72% | Business Research Insights |
| Kindle share of all e-readers sold | 70% | Business Research Insights |
| North America market share | 46% | Business Research Insights |
| Users accessing cloud-synced libraries | 55% | Business Research Insights |

Conservative estimate: if even 1% of Kindle users want to send web articles with images preserved, that's hundreds of thousands of potential users.

## Competitive Landscape

### Direct Competitors

| Competitor | Model | Price | Strengths | Weaknesses |
|-----------|-------|-------|-----------|------------|
| **KTool** | Freemium SaaS | $6.99/mo ($3.99/mo annual) | Browser extensions, mobile apps, newsletters, RSS | Most expensive, no Telegram presence |
| **Push to Kindle** | Freemium | $2.99-4.99/mo | 10 free articles/mo, Chrome extension, mobile apps | Basic extraction, limited free tier |
| **Instapaper** | Premium feature | $5.99/mo | Large user base, reading list integration | Send-to-Kindle became paid Feb 2025, was running at a loss with 100K+ users |
| **Amazon Send to Kindle** | Free (official) | $0 | Native integration, Chrome extension | Drops images — the core problem we solve |
| **dotepub** | Free tool | $0 | Browser bookmarklet, simple | No Kindle integration, basic extraction |
| **FreeConvert/Convertio** | Free/freemium | $0 | Web-based, no signup | Generic converters, no article extraction |

### Telegram Kindle Bots (indirect competitors)

| Bot | Users | Activity | What it does |
|-----|-------|----------|-------------|
| **kindle-calibre-bot** | 10,000+ registered | 15,000 docs/week | Forwards existing ebook files to Kindle via email. Does NOT extract articles from URLs. |
| **Send2KindleBot** | Unknown | Active | Same — file forwarding only |
| **ebook-sender-bot** | Unknown | Active | Same — file forwarding only |
| **ebooktokindle.com** | Unknown | Active | Same — file forwarding only |

**Critical gap: No existing Telegram bot does URL-to-EPUB conversion. All are file forwarders.**

## Market Validation Signals

### 1. The pain is real
- Amazon's Send to Kindle has dropped images for years — confirmed across forums, GitHub issues ([Mercury Parser #591](https://github.com/postlight/mercury-parser/issues/591)), and user complaints ([MobileRead](https://www.mobileread.com/forums/showthread.php?t=319744))
- Multiple open-source projects exist to solve this, confirming demand

### 2. Willingness to pay is proven
- Instapaper had 100K+ users on Kindle feature, concluded it can't be free, priced at $5.99/mo
- KTool charges $6.99/mo successfully
- Push to Kindle charges $2.99-4.99/mo
- Our $4.99/mo is competitive — between Push to Kindle and KTool

### 3. Telegram distribution is underserved
- kindle-calibre-bot: 10K users, 15K docs/week with zero marketing and zero monetization
- This is our floor, not our ceiling
- Telegram's viral sharing mechanics enable organic growth

### 4. Instapaper's pivot is the strongest signal
- A well-funded company with 100K+ Kindle users concluded this feature can't be offered for free
- Infrastructure cost (parsing, image downloading, EPUB generation, emailing) is real
- They priced at $5.99/mo — validates our $4.99/mo

## Pricing Strategy

| Plan | Price | Includes |
|------|-------|---------|
| Free | $0 | 5 lifetime conversions (after Telegram auth) |
| Pro | $4.99/month | Unlimited conversions via Telegram Payments (Stripe provider) |

Positioning: cheaper than Instapaper ($5.99) and KTool ($6.99), comparable to Push to Kindle ($4.99 mobile), but with a fundamentally easier UX (send URL in Telegram, get EPUB back).

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Amazon fixes their image problem | Medium | They've had it for years; even if fixed, our Telegram UX is still simpler |
| Free alternatives (Calibre + manual) | Low | High friction — our value is convenience |
| JS-heavy sites fail extraction | Medium | Playwright fallback for headless rendering |
| Legal concerns (content fetching) | Low | "Personal reading only" disclaimer, no content storage, same as browser extensions |
| Free tier abuse (throwaway accounts) | Low | Tied to Telegram user ID (hard to create throwaway Telegram accounts) |

## Our Advantages

1. **Telegram-first** — no one else does URL-to-EPUB in Telegram
2. **Images preserved** — the core problem Amazon doesn't solve
3. **Zero friction** — send URL, get EPUB. No website, no login forms, no browser extensions to install
4. **Privacy-first** — no EPUB storage, only metadata. Strong differentiator vs. competitors who store content
5. **Telegram identity** — no email/password signup, no verification emails. Telegram user ID = account
6. **Telegram Payments** — native payment flow, no redirect to Stripe checkout pages

## Revenue Projections (Conservative)

| Scenario | Paying users | MRR | ARR |
|----------|-------------|-----|-----|
| Pessimistic (1K paying) | 1,000 | $4,990 | $59,880 |
| Moderate (5K paying) | 5,000 | $24,950 | $299,400 |
| Optimistic (15K paying) | 15,000 | $74,850 | $898,200 |

Based on kindle-calibre-bot achieving 10K users with zero effort, converting even 10-20% of a similar user base to paid would put us in the moderate scenario.

## Sources

- [Amazon Kindle Market Size & Share | CAGR of 4.78%](https://www.businessresearchinsights.com/market-reports/amazon-kindle-market-120402)
- [KTool Pricing](https://ktool.io/pricing)
- [Push to Kindle](https://www.pushtokindle.com/)
- [kindle-calibre-bot — 10K users, 15K docs/week](https://github.com/acamposcar/kindle-calibre-bot)
- [Send2KindleBot](https://github.com/GabrielRF/Send2KindleBot)
- [Instapaper Send to Kindle goes paid](https://goodereader.com/blog/kindle/send-to-kindle-with-instapaper-is-now-going-to-cost-money)
- [Mercury Parser — images not sent issue](https://github.com/postlight/mercury-parser/issues/591)
- [MobileRead — images disappearing from ebooks](https://www.mobileread.com/forums/showthread.php?t=319744)
- [eBook Market Trends](https://www.mordorintelligence.com/industry-reports/e-book-market)
- [Telegram Bot Monetization Guide](https://iimagined.ai/blog/telegram-bot-monetization)
