from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class CallTaskStatus(StrEnum):
    PENDING = "pending"
    DISPATCHING = "dispatching"
    CALLING = "calling"
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"


MAX_ATTEMPTS = 3

ALLOWED_TRANSITIONS: dict[CallTaskStatus, set[CallTaskStatus]] = {
    CallTaskStatus.PENDING: {CallTaskStatus.DISPATCHING},
    CallTaskStatus.DISPATCHING: {CallTaskStatus.CALLING, CallTaskStatus.PENDING},
    CallTaskStatus.CALLING: {
        CallTaskStatus.COMPLETED,
        CallTaskStatus.PENDING,
        CallTaskStatus.EXHAUSTED,
    },
    CallTaskStatus.COMPLETED: set(),
    CallTaskStatus.EXHAUSTED: set(),
}


def can_transition(src: CallTaskStatus, dst: CallTaskStatus) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, set())


def backoff_seconds(attempt: int) -> int:
    return 60 * 2 ** (attempt - 1)


@dataclass
class RetryDecision:
    status: CallTaskStatus
    attempts: int
    next_eligible_at: datetime | None


def plan_retry(current_attempts: int, now: datetime) -> RetryDecision:
    new_attempts = current_attempts + 1
    if new_attempts >= MAX_ATTEMPTS:
        return RetryDecision(CallTaskStatus.EXHAUSTED, new_attempts, None)
    next_at = now + timedelta(seconds=backoff_seconds(new_attempts))
    return RetryDecision(CallTaskStatus.PENDING, new_attempts, next_at)
