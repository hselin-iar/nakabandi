"""store.py — SQLAlchemy models and repositories for experiment runs (DOC 3 B7).

Tables (evaluation module owns these; no other module reads them):
  experiment_runs     — one row per run_experiment() call
  experiment_metrics  — one row per metric value in a run

Repositories follow the standard pattern: __init__(session), never commit().
"""

from __future__ import annotations

import datetime  # noqa: TID251 — store is infrastructure; wall-clock for created_at
import logging
from datetime import UTC
from typing import Any

from sqlalchemy import JSON, Column, Float, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Session

from nakabandi.evaluation.config import ExperimentResult, MetricRow
from nakabandi.shared import new_id

logger = logging.getLogger(__name__)

_UTC = UTC
_utcnow = datetime.datetime.utcnow  # noqa: TID251


# ---------------------------------------------------------------------------
# SQLAlchemy ORM models (evaluation-owned tables)
# ---------------------------------------------------------------------------


class _EvalBase(DeclarativeBase):
    pass


class ExperimentRunModel(_EvalBase):
    """One experiment run."""

    __tablename__ = "experiment_runs"

    id = Column(String(26), primary_key=True)
    config_hash = Column(String(16), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="ok")
    error = Column(Text, nullable=False, default="")
    created_at = Column(String(40), nullable=False)
    config_json = Column(JSON, nullable=False, default=dict)


class ExperimentMetricModel(_EvalBase):
    """One metric value within a run."""

    __tablename__ = "experiment_metrics"

    id = Column(String(26), primary_key=True)
    run_id = Column(String(26), nullable=False, index=True)
    metric = Column(String(64), nullable=False)
    value = Column(Float, nullable=True)
    n = Column(Integer, nullable=False, default=0)
    resolution = Column(String(32), nullable=False, default="")
    baseline = Column(String(64), nullable=False, default="")
    sweep_key = Column(String(128), nullable=False, default="")


# ---------------------------------------------------------------------------
# create_eval_tables helper (called once at startup for the eval process)
# ---------------------------------------------------------------------------


def create_eval_tables(engine: Any) -> None:
    """Create evaluation tables in the given SQLAlchemy engine if not present."""
    _EvalBase.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


class ExperimentRunRepo:
    """Persists and retrieves ExperimentRun records."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, result: ExperimentResult, config_dict: dict[str, Any] | None = None) -> None:
        """Upsert a run by run_id."""
        existing = self._s.get(ExperimentRunModel, result.run_id)
        now_str = _utcnow().isoformat()  # wall-clock for created_at audit field
        if existing is None:
            row = ExperimentRunModel(
                id=result.run_id,
                config_hash=result.config_hash,
                status=result.status,
                error=result.error,
                created_at=now_str,
                config_json=config_dict or {},
            )
            self._s.add(row)
        else:
            existing.status = result.status  # type: ignore[assignment]
            existing.error = result.error  # type: ignore[assignment]

    def get(self, run_id: str) -> ExperimentResult | None:
        """Return an ExperimentResult (without metric rows) by run_id."""
        row = self._s.get(ExperimentRunModel, run_id)
        if row is None:
            return None
        return ExperimentResult(
            run_id=row.id,  # type: ignore[arg-type]
            config_hash=row.config_hash,  # type: ignore[arg-type]
            rows=[],
            status=row.status,  # type: ignore[arg-type]
            error=row.error,  # type: ignore[arg-type]
        )

    def list_all(self) -> list[ExperimentResult]:
        """Return all runs (without metric rows), newest first."""
        stmt = select(ExperimentRunModel).order_by(ExperimentRunModel.created_at.desc())
        rows = self._s.execute(stmt).scalars().all()
        return [
            ExperimentResult(
                run_id=r.id,  # type: ignore[arg-type]
                config_hash=r.config_hash,  # type: ignore[arg-type]
                rows=[],
                status=r.status,  # type: ignore[arg-type]
                error=r.error,  # type: ignore[arg-type]
            )
            for r in rows
        ]


class ExperimentMetricRepo:
    """Persists and retrieves MetricRow records."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def save_rows(self, run_id: str, rows: list[MetricRow]) -> None:
        """Insert metric rows. Caller ensures no duplicates (one run = one call)."""
        for row in rows:
            self._s.add(
                ExperimentMetricModel(
                    id=new_id(),
                    run_id=run_id,
                    metric=row.metric,
                    value=row.value if not __import__("math").isnan(row.value) else None,
                    n=row.n,
                    resolution=row.resolution,
                    baseline=row.baseline,
                    sweep_key=row.sweep_key,
                )
            )

    def get_for_run(self, run_id: str) -> list[MetricRow]:
        """Return all metric rows for a run."""
        stmt = select(ExperimentMetricModel).where(ExperimentMetricModel.run_id == run_id)
        rows = self._s.execute(stmt).scalars().all()
        return [
            MetricRow(
                metric=r.metric,  # type: ignore[arg-type]
                value=r.value if r.value is not None else float("nan"),  # type: ignore[arg-type]
                n=r.n,  # type: ignore[arg-type]
                resolution=r.resolution,  # type: ignore[arg-type]
                baseline=r.baseline,  # type: ignore[arg-type]
                sweep_key=r.sweep_key,  # type: ignore[arg-type]
            )
            for r in rows
        ]
