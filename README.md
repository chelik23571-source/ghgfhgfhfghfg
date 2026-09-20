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
# Or run the entry file directly (including on Windows):
python nft_leads_bot/__main__.py
```

Use the persistent reply-keyboard **🔎 Search** button, choose a category, then use **Next** to consume the already-prefetched batch. **🕘 My history** shows leads already delivered to the current bot operator.

## Diagnostics

The launcher writes detailed diagnostics to the terminal and to `nft_leads_bot.log` in the working directory. The log records each configured chat, scan counts, inaccessible chats, profile-check signals, candidates, and queue actions. Do not publish this file: it can contain Telegram IDs and public usernames.

Each operator has a separate scanned-members list for every category. A later search skips the previously checked profiles and continues checking new visible members. `PROFILE_CHECK_LIMIT` controls how many new full profiles are checked per search (default: 1,000). All matches from that scan are saved to the operator's queue; `BATCH_SIZE` remains the target size shown in scan diagnostics (default: 25).

The scanner does **not** treat ordinary Star Gifts as NFTs. It requests public gifts through `payments.getUserStarGifts` and accepts a profile only when the nested gift has Telegram's exact `StarGiftUnique` type. Fields such as `slug`, `attributes`, and `stargifts_count` do not qualify a profile, because ordinary gifts may expose them too. This detection is included directly in `scanner.py`; copy the complete `nft_leads_bot` folder when deploying.

`SCAN_REVISION` is set to `strict-star-gift-unique-v5`, so the bot rechecks members previously marked as scanned by the old gift detector. Do not change it unless the detection method changes again.
