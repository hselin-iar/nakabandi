"""batches.py — Convert ObservedEvents to LC-1 batch shapes (DOC 3 M1, LC-1).

  to_complaint_batch(complaints, sim_time, batch_id, idem_key) -> ComplaintBatch
  to_hop_batch(hops, sim_time, batch_id, idem_key) -> HopBatch
  to_cashout_batch(cashouts, sim_time, batch_id, idem_key) -> CashOutObservationBatch
  to_registry(registry) -> RegistryUpdate
  to_tick(sim_time) -> Tick

All shapes conform to LC-1. Idempotency key = sha256(f"{seed}:{run_id}:{batch_no}").
Times are `datetime` objects (SimTime = Annotated[datetime, ...]). Helper
`frac_day_to_dt` converts fractional-day floats to aware UTC datetimes.

This module imports from nakabandi_contracts (the contracts package), which is the
ONLY cross-package import allowed for world-sim (DOC 3 M1 shared surfaces).
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta

from nakabandi_contracts.ingest import (
    AccountIn,
    CashOutObservationBatch,
    CashOutObsIn,
    ComplaintBatch,
    ComplaintIn,
    HopBatch,
    HopIn,
    RegistryLocation,
    RegistryUnit,
    RegistryUpdate,
    Tick,
)

from worldsim.core.observe import ObservedCashOut, ObservedComplaint, ObservedHop
from worldsim.core.registry import Registry

# LC-1: batches are capped at 500 items
BATCH_MAX: int = 500

# Sim epoch: all fractional-day times are relative to this UTC moment.
# Defaults to 2026-01-15T06:00:00Z to align with data/seed/mini_ingest.jsonl;
# can be overridden with the WORLDSIM_EPOCH env var.
_SIM_EPOCH_RAW = os.environ.get("WORLDSIM_EPOCH")
_SIM_EPOCH: datetime = (
    datetime.fromisoformat(_SIM_EPOCH_RAW)
    if _SIM_EPOCH_RAW
    else datetime(2026, 1, 15, 6, 0, 0, tzinfo=UTC)
)


def frac_day_to_dt(frac_day: float) -> datetime:
    """Convert fractional-day offset from sim epoch to an aware UTC datetime."""
    return _SIM_EPOCH + timedelta(days=frac_day)


# Keep the internal alias for backwards compatibility within this package
_frac_day_to_iso = frac_day_to_dt


def make_idempotency_key(seed: int, run_id: str, batch_no: int) -> str:
    """Stable idempotency key — same args always yield the same key."""
    raw = f"{seed}:{run_id}:{batch_no}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Conversion functions
# ---------------------------------------------------------------------------


def to_complaint_batch(
    complaints: list[ObservedComplaint],
    sim_time: datetime,
    batch_id: str,
    idem_key: str,
) -> ComplaintBatch:
    items = [
        ComplaintIn(
            external_ref=c.external_ref,
            category=c.category,  # type: ignore[arg-type]
            amount_paise=c.amount_paise,
            victim_district_id=c.district_id,
            credited_at=frac_day_to_dt(c.credited_at),
            reported_event_at=frac_day_to_dt(c.reported_event_at),
            observed_at=frac_day_to_dt(c.observed_at),
            layer1_account=AccountIn(
                account_ref=c.account_id,
                bank_id=c.bank_id,
                home_location_id=c.home_location_id,
            ),
        )
        for c in complaints
    ]
    return ComplaintBatch(
        batch_id=batch_id,
        idempotency_key=idem_key,
        sim_time=sim_time,
        items=items,
    )


def to_hop_batch(
    hops: list[ObservedHop],
    sim_time: datetime,
    batch_id: str,
    idem_key: str,
) -> HopBatch:
    items = [
        HopIn(
            complaint_external_ref=h.complaint_ref,
            from_account=AccountIn(account_ref=h.from_account_id, bank_id=h.from_bank_id),
            to_account=AccountIn(account_ref=h.to_account_id, bank_id=h.to_bank_id),
            amount_paise=h.amount_paise,
            layer=h.layer,
            event_at=frac_day_to_dt(h.event_at),
            observed_at=frac_day_to_dt(h.observed_at),
        )
        for h in hops
    ]
    return HopBatch(
        batch_id=batch_id,
        idempotency_key=idem_key,
        sim_time=sim_time,
        items=items,
    )


def to_cashout_batch(
    cashouts: list[ObservedCashOut],
    sim_time: datetime,
    batch_id: str,
    idem_key: str,
) -> CashOutObservationBatch:
    items = [
        CashOutObsIn(
            account_ref=co.account_id,
            location_id=co.location_id,
            channel=co.channel,  # type: ignore[arg-type]
            amount_paise=co.amount_paise,
            event_at=frac_day_to_dt(co.event_at),
            observed_at=frac_day_to_dt(co.observed_at),
            source="bank_report",
        )
        for co in cashouts
    ]
    return CashOutObservationBatch(
        batch_id=batch_id,
        idempotency_key=idem_key,
        sim_time=sim_time,
        items=items,
    )


def to_registry(registry: Registry, version: str = "v0") -> RegistryUpdate:
    banks = [{"id": b.id, "name": b.name, "short_code": b.short_code} for b in registry.banks]

    # One region row per state (level="state", the Map's boundary polygon join key via
    # geojson_ref) and one per district (level="district", parent_id links it to its state) —
    # nakabandi.geo.domain.parsing.parse_region requires both "level" and "name" on every row.
    states_seen: dict[str, str] = {}
    regions: list[dict] = []
    for d in registry.districts:
        if d.state_id not in states_seen:
            states_seen[d.state_id] = d.state_name
            regions.append(
                {
                    "id": d.state_id,
                    "level": "state",
                    "name": d.state_name,
                    "parent_id": None,
                    "geojson_ref": d.state_id,
                }
            )
        regions.append(
            {
                "id": d.id,
                "level": "district",
                "name": d.name,
                "parent_id": d.state_id,
                "geojson_ref": None,
            }
        )

    cells = [
        {
            "id": c.id,
            "grid_km": c.grid_km,
            "row": c.row,
            "col": c.col,
            "district_id": c.district_id,
            "centroid_lat": c.lat,
            "centroid_lon": c.lon,
        }
        for c in registry.cells
    ]
    locations = [
        RegistryLocation(
            id=loc.id,
            kind=loc.kind,  # type: ignore[arg-type]
            bank_id=loc.bank_id,
            lat=loc.lat,
            lon=loc.lon,
            district_id=loc.district_id,
            cell_id=loc.cell_id,
            source=loc.source,
            display_name=loc.display_name,
            area_type=loc.area_type,  # type: ignore[arg-type]
            activity_index=loc.activity_index,
        )
        for loc in registry.locations
    ]
    units = [
        RegistryUnit(
            id=u.id,
            kind=u.kind,  # type: ignore[arg-type]
            district_id=u.district_id,
            lat=u.lat,
            lon=u.lon,
            status=u.status,
        )
        for u in registry.units
    ]
    return RegistryUpdate(
        version=version,
        banks=banks,
        regions=regions,
        cells=cells,
        locations=locations,
        units=units,
    )


def to_tick(sim_time: datetime) -> Tick:
    return Tick(sim_time=sim_time)
