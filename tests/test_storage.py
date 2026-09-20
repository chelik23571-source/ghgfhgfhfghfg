from pathlib import Path

from nft_leads_bot.storage import Lead, Storage


def test_each_operator_receives_a_lead_only_once(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "leads.sqlite3")
    storage.save_candidates(100, [
        Lead(1, "Alice", "alice", "approved"),
        Lead(2, "Bob", "bob", "approved"),
    ])

    first = storage.next_undelivered(100, "approved")
    assert first is not None and first.telegram_id == 1
    storage.mark_delivered(100, first.telegram_id)

    second = storage.next_undelivered(100, "approved")
    assert second is not None and second.telegram_id == 2
    storage.mark_delivered(100, second.telegram_id)

    assert storage.next_undelivered(100, "approved") is None
    storage.save_candidates(200, [Lead(1, "Alice", "alice", "approved")])
    assert storage.next_undelivered(200, "approved").telegram_id == 1
    assert [lead.telegram_id for lead in storage.history(100)] == [2, 1]


def test_scanned_members_are_tracked_per_operator_and_category(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "leads.sqlite3")
    storage.mark_members_scanned(100, "approved", {1, 2})
    storage.mark_members_scanned(100, "other", {3})
    storage.mark_members_scanned(200, "approved", {4})

    assert storage.scanned_member_ids(100, "approved") == {1, 2}
    assert storage.scanned_member_ids(100, "other") == {3}
    assert storage.scanned_member_ids(200, "approved") == {4}


def test_queue_does_not_return_leads_without_a_username(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "leads.sqlite3")
    storage.save_candidates(100, [
        Lead(1, "Без юзернейма", None, "approved"),
        Lead(2, "С юзернеймом", "named_user", "approved"),
    ])

    lead = storage.next_undelivered(100, "approved")
    assert lead is not None
    assert lead.telegram_id == 2
