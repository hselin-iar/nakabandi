"""SqlRollupRepo: the heat_rollups read model (DOC 3 M3 infrastructure/rollup_repo.py)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nakabandi.analytics.application.ports import BucketSum, RollupDelta
from nakabandi.analytics.infrastructure.models import HeatRollupModel
from nakabandi.shared import SimTime


class SqlRollupRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def current_version(self) -> int:
        top = self._session.scalar(select(func.max(HeatRollupModel.version)))
        return int(top or 0)

    def add(self, deltas: list[RollupDelta]) -> int:
        """Add every delta to its row (creating it), stamp the touched rows with one new version,
        and return that version. One call = one visible change to the map.

        Set-based, not row by row: the deltas are merged by key, the rows that already exist are
        read with ONE query, and the new ones are inserted in one batch. (A forecast has up to a
        couple of hundred deltas; a get-and-flush per delta was the single biggest cost of a
        complaint, measured in the A11 stress run.)"""
        version = self.current_version() + 1
        merged: dict[tuple, RollupDelta] = {}
        for d in deltas:
            key = (
                d.target_kind,
                d.target_id,
                d.hour_bucket,
                d.category,
                d.amount_band,
                d.confidence_band,
                d.layer,
            )
            prior = merged.get(key)
            merged[key] = (
                d
                if prior is None
                else RollupDelta(
                    d.target_kind,
                    d.target_id,
                    d.hour_bucket,
                    d.category,
                    d.amount_band,
                    d.confidence_band,
                    d.layer,
                    prior.mass + d.mass,
                    prior.alert_count + d.alert_count,
                )
            )
        if not merged:
            return version

        m = HeatRollupModel
        existing = {
            (
                r.target_kind,
                r.target_id,
                r.hour_bucket,
                r.category,
                r.amount_band,
                r.confidence_band,
                r.layer,
            ): r
            for r in self._session.scalars(
                select(m).where(
                    m.target_id.in_({k[1] for k in merged}),
                    m.hour_bucket.in_({k[2] for k in merged}),
                    m.layer.in_({k[6] for k in merged}),
                )
            )
        }
        new_rows = []
        for key, d in merged.items():
            row = existing.get(key)
            if row is None:
                new_rows.append(
                    HeatRollupModel(
                        target_kind=d.target_kind,
                        target_id=d.target_id,
                        hour_bucket=d.hour_bucket,
                        category=d.category,
                        amount_band=d.amount_band,
                        confidence_band=d.confidence_band,
                        layer=d.layer,
                        expected_mass=d.mass,
                        alert_count=d.alert_count,
                        version=version,
                    )
                )
            else:
                row.expected_mass += d.mass
                row.alert_count += d.alert_count
                row.version = version
        self._session.add_all(new_rows)
        self._session.flush()
        return version

    def window(
        self,
        *,
        layer: str,
        target_kind: str,
        from_bucket: SimTime,
        to_bucket: SimTime,
        category: str | None = None,
        amount_band: int | None = None,
        min_confidence_band: int | None = None,
    ) -> list[BucketSum]:
        """Sum the window [from_bucket, to_bucket] per (target, hour), across whichever of
        category / amount band / confidence band the filters leave open. One query."""
        m = HeatRollupModel
        q = (
            select(
                m.target_kind,
                m.target_id,
                m.hour_bucket,
                func.sum(m.expected_mass),
                func.sum(m.alert_count),
            )
            .where(
                m.layer == layer,
                m.target_kind == target_kind,
                m.hour_bucket >= from_bucket,
                m.hour_bucket <= to_bucket,
            )
            .group_by(m.target_kind, m.target_id, m.hour_bucket)
        )
        if category is not None:
            q = q.where(m.category == category)
        if amount_band is not None:
            q = q.where(m.amount_band == amount_band)
        if min_confidence_band is not None:
            q = q.where(m.confidence_band >= min_confidence_band)
        return [
            BucketSum(kind, tid, bucket, float(mass), int(count))
            for kind, tid, bucket, mass, count in self._session.execute(q)
        ]
