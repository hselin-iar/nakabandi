"""service.py — BuildEvidencePack use case (DOC 3 S2).

SRP: bundle assembles, hashing hashes, certificate models, pdf renders, service orchestrates.

Masking (DOC 3 S2 testing plan: "bundle contains no unmasked refs for non-LEA roles"): the pack is
built once, by the requesting principal, and is immutable afterwards (DOC 3 S2 "regenerating
creates a new version") — there is no per-viewer re-render, so the account ref shown in the
bundle's summary is masked once, at build time, using the BUILDING principal's own role via
access.mask_ref. Only i4c_analyst, state_investigator, district_officer and admin hold
CREATE_EVIDENCE (config/policy.yaml); district_officer is mask_ref's "non-LEA" tier. A future
per-download re-mask is out of scope here (see docs/state/track-a.md Learnings [A12]).
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from nakabandi.access import Permission, Principal, Role, authorize, mask_ref
from nakabandi.audit import AuditLog
from nakabandi.casework.application.ports import CaseRepo
from nakabandi.casework.evidence.bundle import EvidenceBundle
from nakabandi.casework.evidence.certificate import build_certificate
from nakabandi.casework.evidence.file_store import FileStore
from nakabandi.casework.evidence.hashing import hash_report
from nakabandi.casework.evidence.pdf import render_pdf
from nakabandi.casework.evidence.repo import EvidencePackMeta, EvidencePackRepo
from nakabandi.shared import Clock, Id, new_id


class AlertSource(Protocol):
    """The slice of alerting.AlertService BuildEvidencePack needs (adapted in casework/__init__.py
    so this module never imports the alerting facade directly, mirroring the ClusterSource /
    ComplaintSource pattern in application/ports.py)."""

    def get_alert_for(self, principal: Principal, alert_id: Id) -> Any: ...
    def forecast_for(self, alert: Any) -> object | None: ...
    def assessments_for(self, alert: Any) -> list[object]: ...
    def list_actions(self, alert_id: Id) -> list[Any]: ...
    def list_outcomes(self, alert_id: Id) -> list[Any]: ...


def _view(obj: object) -> Any:
    if obj is None:
        return None
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)  # type: ignore[arg-type]
    return obj


def _enum_val(x: object) -> Any:
    return getattr(x, "value", x)


class BuildEvidencePack:
    def __init__(
        self,
        alert_source: AlertSource,
        case_repo: CaseRepo,
        audit: AuditLog,
        pack_repo: EvidencePackRepo,
        file_store: FileStore,
        role_permissions: Mapping[Role, frozenset[Permission]],
        clock: Clock,
        font_path: Path | None = None,
    ) -> None:
        self._alert_source = alert_source
        self._case_repo = case_repo
        self._audit = audit
        self._pack_repo = pack_repo
        self._file_store = file_store
        self._role_permissions = role_permissions
        self._clock = clock
        self._font_path = font_path

    def run(self, principal: Principal, alert_id: Id) -> EvidencePackMeta:
        authorize(principal, Permission.CREATE_EVIDENCE, self._role_permissions)
        alert = self._alert_source.get_alert_for(principal, alert_id)
        as_of = self._clock.now()

        target_id = (
            mask_ref(alert.target_id, principal)
            if alert.target_kind == "account"
            else alert.target_id
        )
        summary = {
            "alert_id": alert.id,
            "cluster_ref": alert.cluster_ref,
            "target": {"kind": alert.target_kind, "id": target_id, "name": alert.target_name},
            "severity": _enum_val(alert.severity),
            "status": _enum_val(alert.status),
            "ladder_level": _enum_val(alert.ladder_level),
            "created_at": alert.created_at.isoformat(),
        }

        case = self._case_repo.get_by_cluster(alert.cluster_ref)
        case_accounts = (
            [
                {
                    "masked_ref": mask_ref(a.account_ref, principal),
                    "bank_id": a.bank_id,
                    "complaint_count": a.complaint_count,
                }
                for a in case.accounts
            ]
            if case is not None
            else []
        )

        entries = self._audit.list()
        head = self._audit.verify().head_hash or ""
        audit_excerpt = [
            {
                "seq": e.seq,
                "at": e.at.isoformat(),
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "hash": e.hash,
            }
            for e in entries[-50:]
        ]

        bundle = EvidenceBundle(
            alert_id=alert.id,
            generated_at=as_of.isoformat(),
            summary=summary,
            prediction=_view(self._alert_source.forecast_for(alert)),
            interception=[_view(a) for a in self._alert_source.assessments_for(alert)],
            timeline=[
                {
                    "at": t.at.isoformat(),
                    "kind": t.kind,
                    "text_code": t.text_code,
                    "text_params": t.text_params,
                }
                for t in alert.timeline
            ],
            actions=[_view(a) for a in self._alert_source.list_actions(alert.id)],
            outcomes=[_view(o) for o in self._alert_source.list_outcomes(alert.id)],
            audit_excerpt=audit_excerpt,
            audit_head_hash=head,
            case_accounts=case_accounts,
        )

        version = self._pack_repo.latest_version(alert.id) + 1
        report = hash_report({"evidence_bundle.json": bundle.canonical_json()})
        draft = build_certificate(
            record_description=f"Evidence pack for alert {alert.id}, version {version}",
            hash_algorithm=report.algorithm,
            hash_values=[i.sha256 for i in report.items] + [report.bundle_sha256],
        )
        pdf_bytes = render_pdf(bundle, draft, font_path=self._font_path)

        pack_id = new_id()
        storage_path = f"{alert.id}/v{version}/{pack_id}.pdf"
        self._file_store.save(storage_path, pdf_bytes)
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()

        self._audit.append(
            actor_id=principal.user_id,
            actor_role=principal.role.value,
            action="evidence_pack.created",
            entity_type="evidence_pack",
            entity_id=pack_id,
            payload={"alert_id": alert.id, "version": version, "sha256": sha256},
        )
        # The stored head hash is the chain's state INCLUDING this pack's own creation entry
        # (not the pre-append `head` embedded in the bundle content, which cannot reference
        # itself): anyone comparing GET /audit/verify against this value right after the build
        # sees a match, and any tamper anywhere in the chain — including this entry — breaks it.
        sealed_head = self._audit.verify().head_hash or ""

        meta = EvidencePackMeta(
            id=pack_id,
            alert_id=alert.id,
            case_id=case.id if case else None,
            version=version,
            created_at=as_of,
            created_by_role=principal.role.value,
            sha256=sha256,
            size_bytes=len(pdf_bytes),
            audit_head_hash=sealed_head,
            storage_path=storage_path,
        )
        self._pack_repo.save(meta)
        return meta
