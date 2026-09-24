"""Unit tests: build_case totals on a fixture; brief contains the disclaimer and no unmasked
refs; masking in the account-ref list (DOC 3 S1 testing plan)."""

from __future__ import annotations

from datetime import UTC, datetime

from nakabandi.access.domain.masking import mask_ref
from nakabandi.access.domain.principal import Principal, Scope
from nakabandi.casework.domain.brief import render_brief
from nakabandi.casework.domain.bundle import build_case
from nakabandi.casework.domain.case import AccountFact, ClusterSnapshot, ComplaintFact
from nakabandi_contracts.enums import Role

AT = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)


def _snapshot(**overrides: object) -> ClusterSnapshot:
    base: dict[str, object] = dict(
        cluster_id="cl-1",
        as_of=AT,
        complaint_count=2,
        total_paise=4_000_000,
        last_seen_at=AT,
        top_locations=(("loc-1", 6),),
        sub_communities=(),
    )
    base.update(overrides)
    return ClusterSnapshot(**base)  # type: ignore[arg-type]


def test_build_case_totals_two_complaints_one_cluster() -> None:
    complaints = [
        ComplaintFact(
            id="c1",
            external_ref="C1",
            victim_district_id="d1",
            amount_paise=2_000_000,
            reported_event_at=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
            touched_account_ids=("a1", "a2"),
        ),
        ComplaintFact(
            id="c2",
            external_ref="C2",
            victim_district_id="d1",
            amount_paise=2_000_000,
            reported_event_at=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
            touched_account_ids=("a2",),
        ),
    ]
    accounts = [
        AccountFact(account_id="a1", account_ref="1234567890", bank_id="bank-1"),
        AccountFact(account_id="a2", account_ref="9876543210", bank_id="bank-1"),
    ]

    case = build_case(_snapshot(), complaints, accounts, AT)

    assert case.complaint_count == 2
    assert case.victim_count == 2
    assert case.total_paise == 4_000_000
    assert not case.single_complaint
    by_id = {a.account_id: a for a in case.accounts}
    assert by_id["a1"].complaint_count == 1  # only c1 touched a1
    assert by_id["a2"].complaint_count == 2  # both c1 and c2 touched a2
    assert case.built_at == AT


def test_build_case_single_complaint_is_flagged() -> None:
    complaints = [
        ComplaintFact(
            id="c1",
            external_ref="C1",
            victim_district_id="d1",
            amount_paise=2_000_000,
            reported_event_at=AT,
            touched_account_ids=("a1",),
        )
    ]
    accounts = [AccountFact(account_id="a1", account_ref="1234567890", bank_id="bank-1")]

    case = build_case(_snapshot(complaint_count=1), complaints, accounts, AT)

    assert case.single_complaint
    assert case.complaint_count == 1


def test_build_case_rebuild_keeps_existing_id() -> None:
    case1 = build_case(_snapshot(), [], [], AT)
    case2 = build_case(_snapshot(), [], [], AT, existing_id=case1.id)
    assert case2.id == case1.id


def test_brief_states_the_disclaimer_and_no_account_refs() -> None:
    complaints = [
        ComplaintFact(
            id="c1",
            external_ref="C1",
            victim_district_id="d1",
            amount_paise=2_000_000,
            reported_event_at=AT,
            touched_account_ids=("1234567890",),  # deliberately ref-shaped, to prove it never leaks
        )
    ]
    accounts = [AccountFact(account_id="1234567890", account_ref="1234567890", bank_id="bank-1")]
    case = build_case(_snapshot(complaint_count=1), complaints, accounts, AT)

    brief = render_brief(case)

    assert "Whether to register an FIR is the investigating officer's decision." in brief
    assert "1234567890" not in brief  # no raw account ref, masked or not
    assert "guilty" not in brief.lower()


def test_mask_ref_tiers_by_role() -> None:
    full = Principal(user_id="u1", role=Role.I4C_ANALYST, scope=Scope(), display_name="x")
    partial = Principal(user_id="u2", role=Role.DISTRICT_OFFICER, scope=Scope(), display_name="y")

    assert mask_ref("1234567890", full) == "1234567890"
    assert mask_ref("1234567890", partial) == "****7890"
    assert mask_ref("1234567890", partial) != "1234567890"
