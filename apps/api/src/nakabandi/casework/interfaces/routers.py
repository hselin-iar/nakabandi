"""GET /clusters, GET /clusters/{id}, GET /cases, GET /cases/{id}, POST /alerts/{id}/evidence-pack,
GET /evidence-packs/{id}/download (DOC 3 S1, S2).

Routers only parse, authorize and call the casework facade; masking is applied here, at the
interfaces boundary, using access.mask_ref (the domain layer never sees a Principal)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from nakabandi.access import Permission, Principal, authorize, get_principal, mask_ref
from nakabandi.casework.interfaces.deps import build_service, get_uow

router = APIRouter(tags=["casework"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ClusterNodeModel(BaseModel):
    id: str
    kind: str
    masked_ref: str
    bank: str


class ClusterEdgeModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    amount_paise: int | None
    layer: int
    event_at: str


class ClusterModel(BaseModel):
    cluster_ref: str
    size: int
    status: str
    novelty: float
    nodes: list[ClusterNodeModel]
    edges: list[ClusterEdgeModel]


class AccountRefModel(BaseModel):
    masked_ref: str
    bank: str
    complaint_count: int


class LocationHitModel(BaseModel):
    location_id: str
    count: int
    last_at: str


class CaseModel(BaseModel):
    id: str
    cluster_ref: str
    complaint_count: int
    victim_count: int
    total_paise: int
    first_seen: str
    last_seen: str
    accounts: list[AccountRefModel]
    top_locations: list[LocationHitModel]
    sub_communities: list[list[str]]
    brief_md: str
    single_complaint: bool
    built_at: str | None


class CasePageModel(BaseModel):
    items: list[CaseModel]
    next_cursor: str | None


class EvidencePackModel(BaseModel):
    id: str
    alert_id: str
    case_id: str | None
    version: int
    created_at: str
    created_by_role: str
    sha256: str
    size_bytes: int
    audit_head_hash: str
    download_url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cluster_view(graph, principal: Principal) -> ClusterModel:  # noqa: ANN001
    return ClusterModel(
        cluster_ref=graph.cluster_ref,
        size=graph.size,
        status=graph.status,
        novelty=graph.novelty,
        nodes=[
            ClusterNodeModel(
                id=n.id, kind=n.kind, masked_ref=mask_ref(n.account_ref, principal), bank=n.bank_id
            )
            for n in graph.nodes
        ],
        edges=[
            ClusterEdgeModel.model_validate(
                {
                    "from": e.from_id,
                    "to": e.to_id,
                    "amount_paise": e.amount_paise,
                    "layer": e.layer,
                    "event_at": e.event_at.isoformat(),
                }
            )
            for e in graph.edges
        ],
    )


def _case_view(case, principal: Principal) -> CaseModel:  # noqa: ANN001
    return CaseModel(
        id=case.id,
        cluster_ref=case.cluster_ref,
        complaint_count=case.complaint_count,
        victim_count=case.victim_count,
        total_paise=case.total_paise,
        first_seen=case.first_seen.isoformat(),
        last_seen=case.last_seen.isoformat(),
        accounts=[
            AccountRefModel(
                masked_ref=mask_ref(a.account_ref, principal),
                bank=a.bank_id,
                complaint_count=a.complaint_count,
            )
            for a in case.accounts
        ],
        top_locations=[
            LocationHitModel(
                location_id=h.location_id, count=h.count, last_at=h.last_at.isoformat()
            )
            for h in case.top_locations
        ],
        sub_communities=case.sub_communities,
        brief_md=case.brief_md,
        single_complaint=case.single_complaint,
        built_at=case.built_at.isoformat() if case.built_at else None,
    )


def _pack_view(meta) -> EvidencePackModel:  # noqa: ANN001
    return EvidencePackModel(
        id=meta.id,
        alert_id=meta.alert_id,
        case_id=meta.case_id,
        version=meta.version,
        created_at=meta.created_at.isoformat(),
        created_by_role=meta.created_by_role,
        sha256=meta.sha256,
        size_bytes=meta.size_bytes,
        audit_head_hash=meta.audit_head_hash,
        download_url=f"/api/v1/evidence-packs/{meta.id}/download",
    )


# ---------------------------------------------------------------------------
# Routes: clusters and cases (S1)
# ---------------------------------------------------------------------------


@router.get("/clusters", response_model=CasePageModel)
def list_clusters(
    request: Request,
    cursor: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(get_principal),
) -> CasePageModel:
    """Known clusters = clusters that already have a bundled case (DOC 3 S1)."""
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        authorize(principal, Permission.VIEW_CASES, request.app.state.role_permissions)
        cases, next_cursor = svc.list(cursor, min(limit, 200))
    return CasePageModel(items=[_case_view(c, principal) for c in cases], next_cursor=next_cursor)


@router.get("/clusters/{cluster_id}", response_model=ClusterModel)
def get_cluster(
    cluster_id: str, request: Request, principal: Principal = Depends(get_principal)
) -> ClusterModel:
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        authorize(principal, Permission.VIEW_CASES, request.app.state.role_permissions)
        graph = svc.cluster_graph(cluster_id)
    return _cluster_view(graph, principal)


@router.get("/cases", response_model=CasePageModel)
def list_cases(
    request: Request,
    cursor: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(get_principal),
) -> CasePageModel:
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        authorize(principal, Permission.VIEW_CASES, request.app.state.role_permissions)
        cases, next_cursor = svc.list(cursor, min(limit, 200))
    return CasePageModel(items=[_case_view(c, principal) for c in cases], next_cursor=next_cursor)


@router.get("/cases/{case_id}", response_model=CaseModel)
def get_case(
    case_id: str, request: Request, principal: Principal = Depends(get_principal)
) -> CaseModel:
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        authorize(principal, Permission.VIEW_CASES, request.app.state.role_permissions)
        case = svc.get(case_id)
    return _case_view(case, principal)


# ---------------------------------------------------------------------------
# Routes: evidence packs (S2)
# ---------------------------------------------------------------------------


@router.post("/alerts/{alert_id}/evidence-pack", response_model=EvidencePackModel)
def build_evidence_pack(
    alert_id: str, request: Request, principal: Principal = Depends(get_principal)
) -> EvidencePackModel:
    """Authorization (CREATE_EVIDENCE, and VIEW_ALERTS/scope on the underlying alert) happens
    inside the use case, since it needs the alert row to check scope."""
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        meta = svc.build_evidence_pack(principal, alert_id)
        uow.commit()
    return _pack_view(meta)


@router.get("/evidence-packs/{pack_id}", response_model=EvidencePackModel)
def get_evidence_pack(
    pack_id: str, request: Request, principal: Principal = Depends(get_principal)
) -> EvidencePackModel:
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        authorize(principal, Permission.VIEW_CASES, request.app.state.role_permissions)
        meta = svc.get_evidence_pack(pack_id)
    return _pack_view(meta)


@router.get("/evidence-packs/{pack_id}/download")
def download_evidence_pack(
    pack_id: str, request: Request, principal: Principal = Depends(get_principal)
) -> Response:
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        authorize(principal, Permission.VIEW_CASES, request.app.state.role_permissions)
        meta = svc.get_evidence_pack(pack_id)
        data = svc.download_evidence_pack(pack_id)
    filename = f"evidence-pack-{meta.alert_id}-v{meta.version}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
