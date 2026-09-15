from app.core.rate_limit import SlidingWindowRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limit_applies_within_window_and_resets_after() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60, clock=clock)

    assert [limiter.hit("1.2.3.4") for _ in range(4)] == [True, True, True, False]
    assert limiter.hit("5.6.7.8") is True

    clock.now += 61
    assert limiter.hit("1.2.3.4") is True
