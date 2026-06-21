from enum import StrEnum


class CallTaskStatus(StrEnum):
    PENDING = "pending"
    DISPATCHING = "dispatching"
    CALLING = "calling"
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"
