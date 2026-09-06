import time

from errors import AppError


class Deadline:
    def __init__(self, total_s: float, stage: str, timeout_message: str) -> None:
        self._end = time.monotonic() + total_s
        self.stage = stage
        self.timeout_message = timeout_message

    def remaining(self) -> float:
        left = self._end - time.monotonic()
        if left <= 0.05:
            raise AppError(504, "UPSTREAM_TIMEOUT", self.timeout_message, self.stage)
        return left

    def timeout_for(self, budget: float) -> float:
        return min(budget, self.remaining())
