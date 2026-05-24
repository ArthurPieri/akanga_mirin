"""Phase 4 — Debounce pattern using threading.Timer.

Run: python examples/phase_04_debounce_timer.py

Shows how rapid events are coalesced into a single action
after the burst settles. 10 rapid calls → 1 actual execution.

WHY PER-KEY TIMERS MATTER (Phase 04 Common Pitfalls):
A single shared timer means a save to `a.md` resets the debounce
window for `b.md` — the two files interfere with each other.
Using a dict[path → Timer] gives each key its own independent
timer so rapid saves to one file never delay processing of another.
"""
import threading
import time


class Debouncer:
    def __init__(self, delay_s: float, fn):
        self.delay_s = delay_s
        self.fn = fn
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self.call_count = 0
        self._count_lock = threading.Lock()

    def __call__(self, key: str, *args, **kwargs):
        with self._lock:
            existing = self._timers.pop(key, None)
            if existing:
                existing.cancel()
            t = threading.Timer(self.delay_s, self._fire, args=(key, *args), kwargs=kwargs)
            t.daemon = True
            self._timers[key] = t
            t.start()

    def _fire(self, key: str, *args, **kwargs):
        with self._lock:
            self._timers.pop(key, None)
        with self._count_lock:
            self.call_count += 1
        self.fn(key, *args, **kwargs)


# Demonstrate that different keys have independent timers
debouncer = Debouncer(delay_s=0.1, fn=lambda key, *a, **kw: None)
for i in range(5):
    debouncer("file_a.md")   # these should coalesce → 1 fire
for i in range(3):
    debouncer("file_b.md")   # these should coalesce → 1 fire independently
time.sleep(0.3)
# Both keys fired exactly once each
assert debouncer.call_count == 2, f"Expected 2 fires (one per key), got {debouncer.call_count}"
print("✓ Per-key debounce: 8 calls across 2 keys → 2 fires")
