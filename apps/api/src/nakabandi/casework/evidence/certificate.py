"""certificate.py — Section63Draft model and builder (DOC 3 S2). Pure.

The exact field wording is drafted against DOC 3's own section list, not yet against the official
Schedule form's transcription (Track R Step R3 has not landed — DOC 4 Sync 8 gates the FINAL field
labels on it, the same "draft now, revise at Sync 8" pattern DOC 4 already uses for Track D's D4).
Every instance carries the DRAFT label and is never presented as matching the official form.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DRAFT_LABEL = "DRAFT - unsigned drafting aid, not a legal certificate"


@dataclass(frozen=True, slots=True)
class SignatoryPart:
    role: str
    name: str = ""
    designation: str = ""
    qualification: str = ""
    signature: str = ""


@dataclass(frozen=True, slots=True)
class Section63Draft:
    record_description: str
    system_description: str
    production_process: str
    condition_statements: list[str] = field(default_factory=list)
    hash_algorithm: str = "SHA-256"
    hash_values: list[str] = field(default_factory=list)
    part_a: SignatoryPart = field(default_factory=lambda: SignatoryPart(role="person in charge"))
    part_b: SignatoryPart = field(default_factory=lambda: SignatoryPart(role="expert"))
    label: str = DRAFT_LABEL


def build_certificate(
    record_description: str, hash_algorithm: str, hash_values: list[str]
) -> Section63Draft:
    return Section63Draft(
        record_description=record_description,
        system_description=(
            "NAKABANDI: an automated system that ingests bank-fraud complaints and cash-out "
            "reports, computes a forecast and an interception assessment, and raises an alert; "
            "this record is that alert's own evidence trail, drawn from the system's database."
        ),
        production_process=(
            "This document was produced by the evidence-pack service at the time of the request, "
            "assembled from the database records referenced by the hash values below, without "
            "manual editing of the underlying data."
        ),
        condition_statements=[
            "The computer was operating properly at the material time (to be confirmed by the "
            "signatory).",
            "The information was fed into the computer in the ordinary course of its normal "
            "activities (to be confirmed by the signatory).",
            "Throughout the material period the computer was operating properly, or if not, that "
            "no respect in which it was not operating properly, or was out of operation, "
            "affected the document or the accuracy of its contents (to be confirmed by the "
            "signatory).",
        ],
        hash_algorithm=hash_algorithm,
        hash_values=hash_values,
    )
