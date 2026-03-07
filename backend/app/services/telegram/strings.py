"""User-facing string constants for the Telegram bot.

All strings are defined here as constants so they can be replaced
with i18n lookups later (ticket-013).
"""

WELCOME_MESSAGE = (
    "Welcome to Links to EPUB!\n\n"
    "Send me any article URL and I'll convert it to an EPUB file.\n\n"
    "Commands:\n"
    "/help - Usage instructions\n"
    "/settings - Open settings\n"
    "/history - Recent conversions\n"
    "/status - Subscription status\n"
    "/subscribe - Upgrade to premium"
)

HELP_MESSAGE = (
    "How to use this bot:\n\n"
    "1. Send me a link to any article or web page\n"
    "2. I'll convert it to EPUB format\n"
    "3. You'll receive the file right here in the chat\n\n"
    "Supported: any public web page with article content.\n\n"
    "Privacy: Your files are deleted immediately after sending. "
    "We only store metadata (URL, title, timestamps) for your conversion history.\n\n"
    "Disclaimer: This bot is provided as-is. Content conversion depends on "
    "the source page structure and may not always produce perfect results."
)

SETTINGS_MESSAGE = "Tap the button below to open settings:"

SETTINGS_BUTTON_TEXT = "Open Settings"

HISTORY_EMPTY = "You have no conversions yet. Send me a URL to get started!"

HISTORY_HEADER = "Your recent conversions:"

SUBSCRIBE_INVOICE_TITLE = "Links to EPUB Pro"
SUBSCRIBE_INVOICE_DESCRIPTION = "Unlimited article-to-EPUB conversions for 30 days."

SUBSCRIBE_ALREADY_ACTIVE = (
    "You already have an active subscription!\n\n"
    "Plan: Premium\n"
    "Expires: {end}\n\n"
    "Your subscription will not auto-renew. "
    "Use /subscribe again after it expires to renew."
)

SUBSCRIBE_PAYMENT_SUCCESS = (
    "Payment successful! Your premium subscription is now active.\n\n"
    "Plan: Premium\n"
    "Period: {start} - {end}\n\n"
    "You now have unlimited conversions. Enjoy!"
)

SUBSCRIBE_PAYMENT_ERROR = (
    "There was a problem processing your payment. "
    "Please try again or contact support."
)

STATUS_FREE_TIER = (
    "Plan: Free tier\n"
    "Conversions used: {used}/{limit}\n"
    "Remaining: {remaining}"
)

STATUS_FREE_TIER_EXHAUSTED = (
    "Plan: Free tier\n"
    "Conversions used: {used}/{limit}\n\n"
    "You've used all your free conversions.\n"
    "Use /subscribe to upgrade to premium."
)

STATUS_SUBSCRIBED = (
    "Plan: Premium\n"
    "Status: {status}\n"
    "Period: {start} - {end}\n\n"
    "Unlimited conversions included."
)

PROCESSING_MESSAGE = "Processing your link... This may take a moment."

PROCESSING_MULTIPLE = "Processing {count} links... This may take a moment."

NO_URLS_FOUND = "I couldn't find any valid URLs in your message. Please send a link starting with http:// or https://."

FREE_TIER_EXCEEDED = (
    "You've reached your free tier limit of {limit} conversions.\n\n"
    "Use /subscribe to upgrade to premium for unlimited conversions."
)

INVALID_URL = "This URL doesn't look valid. Please send a link starting with http:// or https:// to a public web page."

RATE_LIMITED = (
    "You're converting too fast! "
    "Please try again in {minutes} minute{plural}."
)

ERROR_GENERIC = "Something went wrong. Please try again later."
