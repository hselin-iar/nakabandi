"""A11 unit tests: the rate limiter, metrics, stream gate, auto-pause decision and the nightly
schedule (DOC 2 §2.7 "Public exposure"; DOC 4 A11)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from nakabandi.maintenance import AutoPause, StreamGate, seconds_until, should_pause
from nakabandi.shared import Metrics, SlidingWindowLimiter
from nakabandi.shared.config import (
    HOSTED_AUTO_PAUSE_AFTER_MIN,
    HOSTED_MAX_SSE_STREAMS,
    Settings,
)
from nakabandi.shared.metrics import percentile

T0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, at: datetime = T0) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at

    def advance(self, **kw: float) -> None:
        self.at += timedelta(**kw)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


def test_limiter_allows_up_to_the_limit_per_key_then_refuses() -> None:
    limiter = SlidingWindowLimiter(3, timedelta(minutes=1), FakeClock())

    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]
    assert limiter.allow("b") is True  # another client has its own budget


def test_limiter_window_slides() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(2, timedelta(minutes=1), clock)
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")

    clock.advance(seconds=61)

    assert limiter.allow("a") is True


def test_a_refused_call_does_not_extend_the_penalty() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(1, timedelta(minutes=1), clock)
    limiter.allow("a")
    for _ in range(50):  # hammering while limited records nothing
        clock.advance(seconds=1)
        assert limiter.allow("a") is False

    clock.advance(seconds=11)  # 61 s after the one allowed call

    assert limiter.allow("a") is True


def test_a_limit_of_zero_is_unlimited() -> None:
    limiter = SlidingWindowLimiter(0, timedelta(minutes=1), FakeClock())
    assert not limiter.enabled and all(limiter.allow("a") for _ in range(1000))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("p", "expected"), [(0.5, 3.0), (0.95, 5.0), (0.2, 1.0), (1.0, 5.0), (0.0, 1.0)]
)
def test_percentile_is_nearest_rank(p: float, expected: float) -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0, 5.0], p) == expected


def test_percentile_of_nothing_is_zero() -> None:
    assert percentile([], 0.95) == 0.0


def test_latency_summary_in_milliseconds() -> None:
    metrics = Metrics()
    for seconds in (0.010, 0.020, 0.030, 0.040, 0.100):
        metrics.observe("stage.x", seconds)

    s = metrics.latency("stage.x")

    assert (s.count, round(s.p50_ms), round(s.p95_ms), round(s.max_ms)) == (5, 30, 100, 100)
    assert metrics.latency("never").count == 0


def test_timer_records_even_when_the_block_raises() -> None:
    metrics = Metrics()
    with pytest.raises(RuntimeError), metrics.timer("stage.boom"):
        raise RuntimeError("x")
    assert metrics.latency("stage.boom").count == 1


def test_rate_is_events_per_second_over_the_window_and_decays_to_zero() -> None:
    clock = FakeClock()
    metrics = Metrics(clock=clock, rate_window=timedelta(seconds=60))
    for _ in range(10):
        metrics.incr("events", 5)  # 50 events at t0
    clock.advance(seconds=10)

    assert metrics.rate("events") == pytest.approx(5.0)  # 50 events over 10 s

    clock.advance(seconds=120)
    assert metrics.rate("events") == 0.0  # nothing in the window: idle reads zero
    assert metrics.total("events") == 50  # the running total is kept


def test_a_burst_that_just_began_is_not_divided_by_a_minute_it_has_not_lived() -> None:
    clock = FakeClock()
    metrics = Metrics(clock=clock)
    metrics.incr("events", 30)

    assert metrics.rate("events") == pytest.approx(30.0)  # 30 events in (at least) one second


def test_latency_samples_are_bounded() -> None:
    metrics = Metrics(max_samples=10)
    for i in range(100):
        metrics.observe("s", i / 1000)
    assert metrics.latency("s").count == 10


# ---------------------------------------------------------------------------
# Stream gate and auto-pause
# ---------------------------------------------------------------------------


def test_the_stream_cap_refuses_the_next_stream_and_frees_a_slot_on_close() -> None:
    gate = StreamGate(2, FakeClock())
    assert gate.try_open() and gate.try_open()
    assert gate.try_open() is False
    gate.closed()
    assert gate.try_open() is True and gate.open_streams == 2


def test_a_cap_of_zero_means_unlimited_streams() -> None:
    gate = StreamGate(0, FakeClock())
    assert all(gate.try_open() for _ in range(500))


def test_last_viewer_time_is_now_while_watched_and_frozen_after_the_last_one_leaves() -> None:
    clock = FakeClock()
    gate = StreamGate(0, clock)
    gate.try_open()
    clock.advance(minutes=30)
    assert gate.last_viewer_at == clock.now()  # someone is watching right now
    gate.closed()
    left_at = clock.now()
    clock.advance(minutes=10)
    assert gate.last_viewer_at == left_at


@pytest.mark.parametrize(
    ("viewers", "idle_min", "after_min", "expected"),
    [
        (0, 16, 15, True),
        (0, 15, 15, True),  # at exactly the limit
        (0, 14.9, 15, False),
        (1, 999, 15, False),  # someone is watching
        (0, 999, 0, False),  # switched off
    ],
)
def test_should_pause(viewers: int, idle_min: float, after_min: float, expected: bool) -> None:
    assert (
        should_pause(
            viewers=viewers,
            last_viewer_at=T0 - timedelta(minutes=idle_min),
            now=T0,
            after_min=after_min,
        )
        is expected
    )


def _sim(state: str, calls: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"state": state})
        return httpx.Response(200, json={"status": "ok"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _idle_gate(clock: FakeClock, idle_min: float) -> StreamGate:
    gate = StreamGate(0, clock)
    clock.advance(minutes=idle_min)
    return gate


def test_auto_pause_pauses_a_running_world_after_the_idle_period() -> None:
    clock, calls = FakeClock(), []
    pause = AutoPause(
        _idle_gate(clock, 16), "http://sim/control", 15, clock=clock, client=_sim("running", calls)
    )

    assert pause.tick() == "paused"
    assert calls == ["GET /control/status", "POST /control/pause"]


def test_auto_pause_waits_until_the_idle_period_has_passed() -> None:
    clock, calls = FakeClock(), []
    pause = AutoPause(
        _idle_gate(clock, 5), "http://sim/control", 15, clock=clock, client=_sim("running", calls)
    )

    assert pause.tick() == "waiting" and calls == []


@pytest.mark.parametrize("state", ["paused", "idle", "stalled"])  # world-sim's RunnerState values
def test_auto_pause_only_ever_pauses_a_running_world(state: str) -> None:
    clock, calls = FakeClock(), []
    pause = AutoPause(
        _idle_gate(clock, 20), "http://sim/control", 15, clock=clock, client=_sim(state, calls)
    )

    assert pause.tick() == "not_running" and calls == ["GET /control/status"]


def test_auto_pause_does_not_overrule_a_person_who_resumes_it_during_the_same_absence() -> None:
    clock, calls = FakeClock(), []
    pause = AutoPause(
        _idle_gate(clock, 16), "http://sim/control", 15, clock=clock, client=_sim("running", calls)
    )
    assert pause.tick() == "paused"
    calls.clear()

    assert pause.tick() == "already_handled" and calls == []  # resumed, still nobody watching

    pause._gate.try_open()  # a viewer comes...
    assert pause.tick() == "watched"
    pause._gate.closed()  # ...and leaves
    clock.advance(minutes=16)
    assert pause.tick() == "paused"  # a NEW absence is handled again


def test_auto_pause_is_off_without_a_control_url_or_a_period() -> None:
    clock = FakeClock()
    assert AutoPause(_idle_gate(clock, 99), None, 15, clock=clock).tick() == "off"
    assert AutoPause(_idle_gate(clock, 99), "http://sim/control", 0, clock=clock).tick() == "off"


def test_auto_pause_survives_an_unreachable_simulator() -> None:
    clock = FakeClock()

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    client = httpx.Client(transport=httpx.MockTransport(boom))
    pause = AutoPause(_idle_gate(clock, 20), "http://sim/control", 15, clock=clock, client=client)

    assert pause.tick() == "failed"


# ---------------------------------------------------------------------------
# Schedule and settings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "expected_s"),
    [
        (datetime(2026, 1, 15, 2, 0, tzinfo=UTC), 3600),  # 03:00 is an hour away
        (datetime(2026, 1, 15, 3, 0, tzinfo=UTC), 86400),  # just passed: tomorrow, never zero
        (datetime(2026, 1, 15, 23, 30, tzinfo=UTC), 3.5 * 3600),  # rolls over midnight
    ],
)
def test_seconds_until_the_next_occurrence(now: datetime, expected_s: float) -> None:
    assert seconds_until("03:00", now) == expected_s


def _settings(**env: str) -> Settings:
    base = {"API_SERVICE_KEY": "k", "JWT_SECRET": "j" * 40}
    return Settings(**{**base, **{k: v for k, v in env.items()}})  # type: ignore[arg-type]


def test_hosted_mode_supplies_the_doc_defaults_and_off_means_off(monkeypatch) -> None:  # noqa: ANN001
    for name in ("HOSTED_DEMO", "MAX_SSE_STREAMS", "AUTO_PAUSE_AFTER_MIN", "NIGHTLY_RESET_AT"):
        monkeypatch.delenv(f"NAKABANDI_{name}", raising=False)
    monkeypatch.setenv("API_SERVICE_KEY", "k")
    monkeypatch.setenv("JWT_SECRET", "j" * 40)

    off = Settings()  # type: ignore[call-arg]
    assert (off.effective_max_sse_streams, off.effective_auto_pause_after_min) == (0, 0.0)
    assert off.effective_nightly_reset_at is None and off.effective_control_rate_per_min == 0

    monkeypatch.setenv("NAKABANDI_HOSTED_DEMO", "true")
    on = Settings()  # type: ignore[call-arg]
    assert on.effective_max_sse_streams == HOSTED_MAX_SSE_STREAMS == 25
    assert on.effective_auto_pause_after_min == HOSTED_AUTO_PAUSE_AFTER_MIN == 15.0
    assert on.effective_nightly_reset_at == "03:00" and on.effective_control_rate_per_min > 0

    monkeypatch.setenv("NAKABANDI_MAX_SSE_STREAMS", "3")  # an explicit setting beats the default
    monkeypatch.setenv("NAKABANDI_NIGHTLY_RESET_AT", "")  # and "" switches one off
    tuned = Settings()  # type: ignore[call-arg]
    assert tuned.effective_max_sse_streams == 3 and tuned.effective_nightly_reset_at is None


def test_a_malformed_reset_time_stops_the_boot(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("API_SERVICE_KEY", "k")
    monkeypatch.setenv("JWT_SECRET", "j" * 40)
    monkeypatch.setenv("NAKABANDI_NIGHTLY_RESET_AT", "25:99")
    with pytest.raises(ValueError, match="HH:MM"):
        Settings()  # type: ignore[call-arg]
