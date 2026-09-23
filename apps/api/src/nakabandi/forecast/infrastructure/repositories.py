"""repositories.py — SQLAlchemy ForecastRepo implementation (DOC 3 M2).

Tables owned by the forecast module (DOC 3 LC-10):
  forecasts           (id, complaint_id, cluster_id, generated_at, model_versions_json,
                        confidence, novelty, stale, timing_json, evidence_json)
  forecast_level_items (id, forecast_id, resolution, abstained, confidence, items_json)
  model_versions       (id, name, version, params_json, created_at)
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from nakabandi_contracts.enums import Resolution
from sqlalchemy.orm import Session

from nakabandi.forecast.application.ports import ForecastRepo
from nakabandi.forecast.domain.types import (
    EvidenceStatement,
    Forecast,
    LevelForecast,
    RankedItem,
    TimingForecast,
)
from nakabandi.shared import Id, SimTime

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

metadata = sa.MetaData()

forecasts_table = sa.Table(
    "forecasts",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("complaint_id", sa.String, nullable=False, index=True),
    sa.Column("cluster_id", sa.String, nullable=True),
    sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("model_versions_json", sa.Text, nullable=False, default="{}"),
    sa.Column("confidence", sa.Float, nullable=False),
    sa.Column("novelty", sa.Float, nullable=False),
    sa.Column("stale", sa.Boolean, nullable=False),
    sa.Column("timing_json", sa.Text, nullable=False, default="{}"),
    sa.Column("evidence_json", sa.Text, nullable=False, default="[]"),
)

forecast_level_items_table = sa.Table(
    "forecast_level_items",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("forecast_id", sa.String, nullable=False, index=True),
    sa.Column("resolution", sa.String, nullable=False),
    sa.Column("abstained", sa.Boolean, nullable=False),
    sa.Column("confidence", sa.Float, nullable=False),
    sa.Column("items_json", sa.Text, nullable=False, default="[]"),
)

# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class SqlForecastRepo(ForecastRepo):
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, forecast: Forecast) -> None:
        # Insert forecast header
        self._s.execute(
            sa.insert(forecasts_table)
            .values(
                id=forecast.id,
                complaint_id=forecast.complaint_id,
                cluster_id=forecast.cluster_id,
                generated_at=forecast.generated_at,
                model_versions_json=json.dumps(forecast.model_versions),
                confidence=forecast.confidence,
                novelty=forecast.novelty,
                stale=forecast.stale,
                timing_json=_timing_to_json(forecast.timing),
                evidence_json=json.dumps(
                    [
                        {"code": e.code, "params": e.params, "text_en": e.text_en}
                        for e in forecast.evidence
                    ]
                ),
            )
            .prefix_with("OR IGNORE")
        )
        # Insert level items
        from nakabandi.shared import new_id as _new_id

        for res_key, level in forecast.levels.items():
            self._s.execute(
                sa.insert(forecast_level_items_table)
                .values(
                    id=_new_id(),
                    forecast_id=forecast.id,
                    resolution=res_key,
                    abstained=level.abstained,
                    confidence=level.confidence,
                    items_json=json.dumps(
                        [
                            {"id": item.id, "prob": item.prob, "rank": item.rank}
                            for item in level.items
                        ]
                    ),
                )
                .prefix_with("OR IGNORE")
            )

    def get_by_complaint(self, complaint_id: Id, as_of: SimTime) -> Forecast | None:
        row = self._s.execute(
            sa.select(forecasts_table)
            .where(
                forecasts_table.c.complaint_id == complaint_id,
                forecasts_table.c.generated_at <= as_of,
            )
            .order_by(forecasts_table.c.generated_at.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        return self._row_to_forecast(row)

    def get_latest(self, complaint_id: Id) -> Forecast | None:
        row = self._s.execute(
            sa.select(forecasts_table)
            .where(forecasts_table.c.complaint_id == complaint_id)
            .order_by(forecasts_table.c.generated_at.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        return self._row_to_forecast(row)

    def _row_to_forecast(self, row: sa.Row) -> Forecast:  # type: ignore[type-arg]
        # Load levels
        level_rows = self._s.execute(
            sa.select(forecast_level_items_table).where(
                forecast_level_items_table.c.forecast_id == row.id
            )
        ).all()
        levels: dict[str, LevelForecast] = {}
        for lr in level_rows:
            items_data = json.loads(lr.items_json)
            resolution = Resolution(lr.resolution)
            levels[lr.resolution] = LevelForecast(
                resolution=resolution,
                abstained=bool(lr.abstained),
                confidence=float(lr.confidence),
                items=[
                    RankedItem(id=i["id"], prob=float(i["prob"]), rank=int(i["rank"]))
                    for i in items_data
                ],
            )

        timing_data = json.loads(row.timing_json)
        timing = TimingForecast(
            weights=timing_data["weights"],
            medians_min=timing_data["medians_min"],
            sigmas=timing_data["sigmas"],
            elapsed_min=float(timing_data["elapsed_min"]),
            residual_mass=float(timing_data["residual_mass"]),
            p30=float(timing_data["p30"]),
            p60=float(timing_data["p60"]),
            p120=float(timing_data["p120"]),
        )

        evidence_data = json.loads(row.evidence_json)
        evidence = [
            EvidenceStatement(
                code=e["code"], params=e.get("params", {}), text_en=e.get("text_en", "")
            )
            for e in evidence_data
        ]

        return Forecast(
            id=row.id,
            complaint_id=row.complaint_id,
            cluster_id=row.cluster_id,
            generated_at=row.generated_at,
            model_versions=json.loads(row.model_versions_json),
            levels=levels,
            timing=timing,
            confidence=float(row.confidence),
            novelty=float(row.novelty),
            stale=bool(row.stale),
            evidence=evidence,
        )


def _timing_to_json(t: TimingForecast) -> str:
    return json.dumps(
        {
            "weights": t.weights,
            "medians_min": t.medians_min,
            "sigmas": t.sigmas,
            "elapsed_min": t.elapsed_min,
            "residual_mass": t.residual_mass,
            "p30": t.p30,
            "p60": t.p60,
            "p120": t.p120,
        }
    )
