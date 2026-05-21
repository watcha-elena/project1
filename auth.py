import time
from typing import Callable, Optional


class LoginRateLimiter:
    """브라우저 세션 단위의 로그인 시도 제한.

    Streamlit `st.session_state`에 인스턴스를 보관해 사용.
    `now` 인자는 테스트에서 시간을 주입할 수 있게 의존성 분리.
    """

    def __init__(
        self,
        max_failures: int = 5,
        lockout_seconds: int = 300,
        now: Callable[[], float] = time.time,
    ):
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self._now = now
        self._failure_count = 0
        self._lockout_started_at: Optional[float] = None

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.max_failures and self._lockout_started_at is None:
            self._lockout_started_at = self._now()

    def record_success(self) -> None:
        self._failure_count = 0
        self._lockout_started_at = None

    def is_locked(self) -> bool:
        return self.remaining_lockout_seconds() > 0

    def remaining_lockout_seconds(self) -> int:
        if self._lockout_started_at is None:
            return 0
        elapsed = self._now() - self._lockout_started_at
        remaining = self.lockout_seconds - elapsed
        if remaining <= 0:
            # 잠금 자동 해제
            self._failure_count = 0
            self._lockout_started_at = None
            return 0
        return int(remaining)

    @property
    def remaining_attempts(self) -> int:
        """남은 시도 횟수 (0이면 잠금)."""
        return max(0, self.max_failures - self._failure_count)
