"""Policy.load() validates every key; unknown or missing key aborts boot
(DOC 3 Shared Kernel TESTING PLAN and EDGE CASES)."""

from pathlib import Path

import pytest
import yaml
from nakabandi.shared import Policy, PolicyLoadError

REPO_ROOT = Path(__file__).resolve().parents[4]
POLICY_PATH = REPO_ROOT / "config" / "policy.yaml"


def test_the_real_policy_yaml_loads() -> None:
    policy = Policy.load(POLICY_PATH)
    assert policy.interception.thresholds.interceptable == 0.7
    assert policy.forecast.horizons_min == [30, 60, 120]
    assert "i4c_analyst" in policy.access.permissions


def test_missing_file_aborts_boot() -> None:
    with pytest.raises(PolicyLoadError):
        Policy.load(REPO_ROOT / "config" / "does-not-exist.yaml")


def test_missing_key_aborts_boot(tmp_path: Path) -> None:
    raw = yaml.safe_load(POLICY_PATH.read_text())
    del raw["interception"]["thresholds"]["marginal"]
    bad = tmp_path / "policy.yaml"
    bad.write_text(yaml.safe_dump(raw))
    with pytest.raises(PolicyLoadError, match="interception.*thresholds.*marginal"):
        Policy.load(bad)


def test_extra_key_aborts_boot(tmp_path: Path) -> None:
    raw = yaml.safe_load(POLICY_PATH.read_text())
    raw["forecast"]["not_a_real_key"] = 1
    bad = tmp_path / "policy.yaml"
    bad.write_text(yaml.safe_dump(raw))
    with pytest.raises(PolicyLoadError):
        Policy.load(bad)


def test_mistyped_key_aborts_boot(tmp_path: Path) -> None:
    raw = yaml.safe_load(POLICY_PATH.read_text())
    raw["interception"]["targets"] = "three"  # should be an int
    bad = tmp_path / "policy.yaml"
    bad.write_text(yaml.safe_dump(raw))
    with pytest.raises(PolicyLoadError, match="interception.*targets"):
        Policy.load(bad)


def test_invalid_yaml_aborts_boot(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text("forecast: [unbalanced")
    with pytest.raises(PolicyLoadError):
        Policy.load(bad)


def test_ladder_without_catch_all_is_rejected(tmp_path: Path) -> None:
    raw = yaml.safe_load(POLICY_PATH.read_text())
    raw["interception"]["ladder"] = [{"channel": "ATM", "verdict": "MARGINAL", "level": "L1"}]
    bad = tmp_path / "policy.yaml"
    bad.write_text(yaml.safe_dump(raw))
    with pytest.raises(PolicyLoadError):
        Policy.load(bad)


def test_unknown_role_in_permissions_is_rejected(tmp_path: Path) -> None:
    raw = yaml.safe_load(POLICY_PATH.read_text())
    raw["access"]["permissions"]["not_a_role"] = ["VIEW_ALERTS"]
    bad = tmp_path / "policy.yaml"
    bad.write_text(yaml.safe_dump(raw))
    with pytest.raises(PolicyLoadError):
        Policy.load(bad)
