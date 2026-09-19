from pathlib import Path

from nft_leads_bot.storage import Lead, Storage


def test_each_operator_receives_a_lead_only_once(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "leads.sqlite3")
    storage.save_candidates([
        Lead(1, "Alice", "alice", "approved"),
        Lead(2, "Bob", None, "approved"),
    ])

    first = storage.next_undelivered(100, "approved")
    assert first is not None and first.telegram_id == 1
    storage.mark_delivered(100, first.telegram_id)

    second = storage.next_undelivered(100, "approved")
    assert second is not None and second.telegram_id == 2
    storage.mark_delivered(100, second.telegram_id)

    assert storage.next_undelivered(100, "approved") is None
    assert storage.next_undelivered(200, "approved").telegram_id == 1
    assert [lead.telegram_id for lead in storage.history(100)] == [2, 1]
