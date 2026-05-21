from auth import LoginRateLimiter


def test_initially_not_locked():
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: 0.0)
    assert not limiter.is_locked()
    assert limiter.remaining_lockout_seconds() == 0


def test_below_threshold_not_locked():
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: 0.0)
    for _ in range(4):
        limiter.record_failure()
    assert not limiter.is_locked()


def test_locked_at_threshold():
    t = [0.0]
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: t[0])
    for _ in range(5):
        limiter.record_failure()
    assert limiter.is_locked()
    assert limiter.remaining_lockout_seconds() == 300


def test_lockout_expires():
    t = [0.0]
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: t[0])
    for _ in range(5):
        limiter.record_failure()
    t[0] = 301.0
    assert not limiter.is_locked()
    assert limiter.remaining_lockout_seconds() == 0


def test_success_resets_counter():
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: 0.0)
    for _ in range(4):
        limiter.record_failure()
    limiter.record_success()
    for _ in range(4):
        limiter.record_failure()
    assert not limiter.is_locked()


def test_remaining_lockout_decreases_with_time():
    t = [0.0]
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: t[0])
    for _ in range(5):
        limiter.record_failure()
    t[0] = 100.0
    assert limiter.remaining_lockout_seconds() == 200


def test_remaining_attempts_property():
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: 0.0)
    assert limiter.remaining_attempts == 5
    limiter.record_failure()
    assert limiter.remaining_attempts == 4
    for _ in range(4):
        limiter.record_failure()
    assert limiter.remaining_attempts == 0
