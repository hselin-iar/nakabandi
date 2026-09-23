"""lien.py — LienProposal value object with invariants, and build_lien() (DOC 3 M6).

KEY INVARIANTS (DOC 3, AGENTS.md "NEVER" rules):
  - proposed_paise > 0
  - proposed_paise <= disputed_paise
  - expires_at > review_at > now
  - complaint_id must be present (non-empty)
  - account_id must belong to the complaint's traced accounts
  - NO field or constructor for a whole-account freeze

build_lien() enforces the total-cap rule: the sum of proposed amounts for a
single complaint across all active liens cannot exceed disputed_paise.
"""

from __future__ import annotations

from dataclasses import dataclass

from nakabandi.shared import Id, Policy, SimTime, ValidationFailed


class LienInvalid(ValidationFailed):
    """Raised when a LienProposal cannot be constructed due to invariant violations."""


@dataclass(frozen=True)
class LienProposal:
    """Immutable value object representing a proposed partial lien on one account.

    Construction validates all invariants; LienInvalid is raised on any violation.

    Fields
    ------
    complaint_id:     The complaint this lien is anchored to (must be non-empty).
    account_id:       The mule account to hold funds in (must be in traced_accounts).
    disputed_paise:   Total traced credit into this account from the complaint.
    proposed_paise:   Amount to hold (0 < proposed <= disputed).
    expires_at:       When the hold lapses automatically (> review_at).
    review_at:        Magistrate review deadline (> now at construction time).

    There is NO field for a whole-account freeze (DOC 3, AGENTS.md NEVER clause).
    """

    complaint_id: Id
    account_id: Id
    disputed_paise: int
    proposed_paise: int
    expires_at: SimTime
    review_at: SimTime

    def __post_init__(self) -> None:
        errors: list[str] = []
        if not self.complaint_id:
            errors.append("complaint_id must be non-empty")
        if not self.account_id:
            errors.append("account_id must be non-empty")
        if self.disputed_paise <= 0:
            errors.append(f"disputed_paise must be > 0, got {self.disputed_paise}")
        if self.proposed_paise <= 0:
            errors.append(f"proposed_paise must be > 0, got {self.proposed_paise}")
        if self.proposed_paise > self.disputed_paise:
            errors.append(
                f"proposed_paise ({self.proposed_paise}) must be <= "
                f"disputed_paise ({self.disputed_paise})"
            )
        if self.review_at >= self.expires_at:
            errors.append("review_at must be before expires_at")
        if errors:
            raise LienInvalid("LIEN_INVALID", "; ".join(errors))


def build_lien(
    complaint_id: Id,
    account_id: Id,
    traced_accounts: list[Id],
    disputed_paise: int,
    active_lien_proposed_total: int,
    policy: Policy,
    now: SimTime,
) -> LienProposal | None:
    """Construct a LienProposal, or return None if nothing can be held.

    DOC 3 M6 rules:
      - proposed = disputed - already_proposed_for_this_complaint
        (the total proposed across all active liens for this complaint cannot exceed disputed)
      - If account_id is not in traced_accounts: return None
      - If disputed_paise == 0 or remaining == 0: return None
      - expires_at = now + lien.expiry_hours (from policy)
      - review_at  = now + lien.review_hours  (from policy)

    Parameters
    ----------
    complaint_id:
        Complaint anchor.
    account_id:
        Account to hold.
    traced_accounts:
        All accounts traced to this complaint.  account_id must be in this list.
    disputed_paise:
        Total amount traced into account_id from this complaint.
    active_lien_proposed_total:
        Sum of proposed_paise across all existing active liens for this complaint.
    policy:
        The loaded Policy object (reads lien.expiry_hours, lien.review_hours).
    now:
        Current sim time (LC-2 — never datetime.now(); injected by use case).
    """
    from datetime import timedelta

    if account_id not in traced_accounts:
        return None
    if disputed_paise <= 0:
        return None

    remaining = disputed_paise - active_lien_proposed_total
    if remaining <= 0:
        return None

    proposed = remaining  # hold everything that can still be held

    expiry_hours = policy.lien.expiry_hours
    review_hours = policy.lien.review_hours
    expires_at = now + timedelta(hours=expiry_hours)
    review_at = now + timedelta(hours=review_hours)

    return LienProposal(
        complaint_id=complaint_id,
        account_id=account_id,
        disputed_paise=disputed_paise,
        proposed_paise=proposed,
        expires_at=expires_at,
        review_at=review_at,
    )
