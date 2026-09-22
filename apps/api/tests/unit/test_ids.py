"""new_id(): sortable, no arguments, no state (DOC 3 Shared Kernel TESTING PLAN)."""

from nakabandi.shared import new_id


def test_new_id_is_sortable_and_unique() -> None:
    ids = [new_id() for _ in range(50)]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_new_id_takes_no_arguments() -> None:
    assert isinstance(new_id(), str)
