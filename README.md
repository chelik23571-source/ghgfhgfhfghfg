# NFT lead inbox for Telegram

A small **Aiogram 3 + Telethon** application for a community administrator to deliver opted-in members with publicly exposed profile collectibles to an internal bot inbox. It maintains a per-operator delivery history and pre-fills a queue, so **Next** does not start a new scan.

## Privacy and Telegram limits

Use this only in communities you administer, for members who have opted in, and only with a clear notice describing the purpose and retention period. The scanner intentionally:

- reads Telegram's visible participant list only;
- does **not** scrape message history to reconstruct a hidden member list;
- does not bypass privacy settings;
- ignores users where a public collectible signal cannot be determined by the installed Telegram API layer.

Telegram's available collectible fields vary by client/API version. Update Telethon when Telegram exposes a supported public profile-collectibles field.

## Setup

1. Create a Telegram bot with BotFather and obtain API credentials at `my.telegram.org`.
2. Open `nft_leads_bot/__main__.py` and replace the placeholder constants at the top: `BOT_TOKEN`, `TELETHON_API_ID`, `TELETHON_API_HASH`, `TELETHON_SESSION_STRING`, and `CATEGORIES`. Create the Telethon string session locally with your own authorized account; never publish it.
3. Put only approved, opted-in community chat IDs in the `CATEGORIES` constant.
4. Install and run:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python -m nft_leads_bot
```

Use the persistent reply-keyboard **🔎 Search** button, choose a category, then use **Next** to consume the already-prefetched batch. **🕘 My history** shows leads already delivered to the current bot operator.
