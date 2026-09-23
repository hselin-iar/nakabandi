"""model_store.py — joblib model persistence + metadata + fallback detection (DOC 3 M2 B6).

ModelStore:
  save_scorer(scorer, data_hash, as_of)  -> model_version_id
  load_scorer()                          -> HistGradientBoostingScorer | None
  save_timing(model, data_hash, as_of)   -> model_version_id
  load_timing()                          -> MixtureTimingModel | None

Model files live in config.model_store_dir (from policy):
  {model_store_dir}/scorer_latest.joblib
  {model_store_dir}/scorer_latest_meta.json
  {model_store_dir}/timing_latest.joblib
  {model_store_dir}/timing_latest_meta.json

If any file is missing, load_* returns None and the caller falls back to the
heuristic / global mixture scorer with a visible banner.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import joblib

from nakabandi.forecast.application.ports import ModelStorePort
from nakabandi.shared import SimTime, new_id

if TYPE_CHECKING:
    from nakabandi.forecast.domain.scorers import HistGradientBoostingScorer
    from nakabandi.forecast.domain.timing import MixtureTimingModel

logger = logging.getLogger(__name__)

_UTC = datetime.utcnow  # noqa: TID251 — model store is infrastructure, no injected Clock


@dataclass(frozen=True)
class ModelVersionMeta:
    """Metadata persisted alongside every model file."""

    version_id: str
    name: str  # "hgb_v1" | "mixture_v1"
    data_hash: str  # SHA-256 of the training set (for reproducibility)
    trained_as_of: str  # ISO datetime of as_of_end used for training
    created_at: str  # wall-clock ISO (not sim time)
    brier_before: float | None = None
    brier_after: float | None = None


class ModelStore(ModelStorePort):
    """Filesystem-backed model store (joblib + JSON metadata).

    Implements ModelStorePort so it can be injected into TrainModels
    and GenerateForecast at the composition root.
    Thread-safety: single-writer (only TrainModels writes); multiple readers.
    """

    def __init__(self, store_dir: str | Path = "models") -> None:
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Scorer
    # ------------------------------------------------------------------

    def save_scorer(
        self,
        scorer: HistGradientBoostingScorer,  # type: ignore[name-defined]  # noqa: F821
        data_hash: str,
        as_of: SimTime,
        brier_before: float | None = None,
        brier_after: float | None = None,
    ) -> str:
        """Persist scorer to disk. Returns the new version_id."""
        version_id = new_id()
        meta = ModelVersionMeta(
            version_id=version_id,
            name="hgb_v1",
            data_hash=data_hash,
            trained_as_of=as_of.isoformat(),
            created_at=datetime.utcnow().isoformat(),  # noqa: TID251
            brier_before=brier_before,
            brier_after=brier_after,
        )
        joblib.dump(scorer, self._dir / "scorer_latest.joblib")
        (self._dir / "scorer_latest_meta.json").write_text(json.dumps(asdict(meta), indent=2))
        logger.info(
            "model_store.scorer_saved version_id=%s data_hash=%s",
            version_id,
            data_hash,
        )
        return version_id

    def load_scorer(self) -> HistGradientBoostingScorer | None:
        scorer_path = self._dir / "scorer_latest.joblib"
        meta_path = self._dir / "scorer_latest_meta.json"
        if not scorer_path.exists() or not meta_path.exists():
            logger.warning("model_store.scorer_missing path=%s — using fallback", scorer_path)
            return None
        try:
            scorer = joblib.load(scorer_path)
            meta = json.loads(meta_path.read_text())
            logger.info(
                "model_store.scorer_loaded version_id=%s data_hash=%s",
                meta.get("version_id"),
                meta.get("data_hash"),
            )
            return scorer  # type: ignore[return-value]
        except Exception as exc:
            logger.error("model_store.scorer_load_failed error=%s — using fallback", str(exc))
            return None

    def scorer_meta(self) -> ModelVersionMeta | None:
        """Return the metadata of the currently stored scorer, or None."""
        meta_path = self._dir / "scorer_latest_meta.json"
        if not meta_path.exists():
            return None
        try:
            return ModelVersionMeta(**json.loads(meta_path.read_text()))
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Timing model
    # ------------------------------------------------------------------

    def save_timing(
        self,
        model: MixtureTimingModel,  # type: ignore[name-defined]  # noqa: F821
        data_hash: str,
        as_of: SimTime,
    ) -> str:
        """Persist timing model to disk. Returns the new version_id."""
        version_id = new_id()
        meta = ModelVersionMeta(
            version_id=version_id,
            name="mixture_v1",
            data_hash=data_hash,
            trained_as_of=as_of.isoformat(),
            created_at=datetime.utcnow().isoformat(),  # noqa: TID251
        )
        joblib.dump(model, self._dir / "timing_latest.joblib")
        (self._dir / "timing_latest_meta.json").write_text(json.dumps(asdict(meta), indent=2))
        logger.info("model_store.timing_saved version_id=%s", version_id)
        return version_id

    def load_timing(self) -> MixtureTimingModel | None:
        """Load the timing model from disk. Returns None if files are missing."""
        timing_path = self._dir / "timing_latest.joblib"
        meta_path = self._dir / "timing_latest_meta.json"
        if not timing_path.exists() or not meta_path.exists():
            logger.warning("model_store.timing_missing path=%s — using global mixture", timing_path)
            return None
        try:
            model = joblib.load(timing_path)
            meta = json.loads(meta_path.read_text())
            logger.info("model_store.timing_loaded version_id=%s", meta.get("version_id"))
            return model  # type: ignore[return-value]
        except Exception as exc:
            logger.error("model_store.timing_load_failed error=%s — using global mixture", str(exc))
            return None

    def timing_meta(self) -> ModelVersionMeta | None:
        meta_path = self._dir / "timing_latest_meta.json"
        if not meta_path.exists():
            return None
        try:
            return ModelVersionMeta(**json.loads(meta_path.read_text()))
        except Exception:
            return None
