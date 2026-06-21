from datetime import datetime, timedelta, timezone

from common.call_task import (
    MAX_ATTEMPTS,
    CallTaskStatus,
    backoff_seconds,
    can_transition,
    plan_retry,
)


def test_backoff_is_exponential():
    assert backoff_seconds(1) == 60
    assert backoff_seconds(2) == 120
    assert backoff_seconds(3) == 240


def test_allowed_transitions():
    assert can_transition(CallTaskStatus.PENDING, CallTaskStatus.DISPATCHING)
    assert can_transition(CallTaskStatus.DISPATCHING, CallTaskStatus.CALLING)
    assert can_transition(CallTaskStatus.CALLING, CallTaskStatus.COMPLETED)
    assert can_transition(CallTaskStatus.CALLING, CallTaskStatus.PENDING)  # retry
    assert can_transition(CallTaskStatus.CALLING, CallTaskStatus.EXHAUSTED)


def test_forbidden_transitions():
    assert not can_transition(CallTaskStatus.PENDING, CallTaskStatus.CALLING)
    assert not can_transition(CallTaskStatus.COMPLETED, CallTaskStatus.PENDING)
    assert not can_transition(CallTaskStatus.EXHAUSTED, CallTaskStatus.PENDING)


def test_plan_retry_schedules_next_attempt():
    now = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    decision = plan_retry(current_attempts=0, now=now)
    assert decision.status == CallTaskStatus.PENDING
    assert decision.attempts == 1
    assert decision.next_eligible_at == now + timedelta(seconds=60)


def test_plan_retry_exhausts_after_max_attempts():
    now = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    decision = plan_retry(current_attempts=MAX_ATTEMPTS - 1, now=now)
    assert decision.status == CallTaskStatus.EXHAUSTED
    assert decision.attempts == MAX_ATTEMPTS
    assert decision.next_eligible_at is None
