"""Phase 4 — Debounce pattern using threading.Timer.

Run: python examples/phase_04_debounce_timer.py

Shows how rapid events are coalesced into a single action
after the burst settles. 8 rapid calls across 2 keys → 2 actual executions (1 per key).

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
        self._pending: dict[str, tuple[float, tuple, dict]] = {}
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self.call_count = 0
        self._count_lock = threading.Lock()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def __call__(self, key: str, *args, **kwargs):
        with self._lock:
            # Update the scheduled fire time for this key
            self._pending[key] = (time.time() + self.delay_s, args, kwargs)
            self._condition.notify()

    def _run(self):
        while True:
            with self._lock:
                if not self._pending:
                    self._condition.wait()
                    continue
                
                now = time.time()
                next_fire = min(item[0] for item in self._pending.values())
                
                if next_fire > now:
                    self._condition.wait(next_fire - now)
                    continue
                
                # Identify the key that is ready to fire
                key = min(self._pending, key=lambda k: self._pending[k][0])
                _, args, kwargs = self._pending.pop(key)
                
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
