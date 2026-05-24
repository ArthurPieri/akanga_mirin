"""Phase 4 — Debounce pattern using threading.Timer.

Run: python examples/phase_04_debounce_timer.py

Shows how rapid events are coalesced into a single action
after the burst settles. 10 rapid calls → 1 actual execution.
"""
import threading
import time


class Debouncer:
    def __init__(self, delay_s: float, fn):
        self.delay_s = delay_s
        self.fn = fn
        self._timer = None
        self._lock = threading.Lock()
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.delay_s, self._fire, args=args, kwargs=kwargs)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self, *args, **kwargs):
        self.call_count += 1
        self.fn(*args, **kwargs)


executions = []
debounced = Debouncer(0.2, executions.append)

print("Firing 10 rapid events...")
for i in range(10):
    debounced(f"event-{i}")
    time.sleep(0.01)

time.sleep(0.4)
print(f"10 rapid events → {len(executions)} execution(s): {executions}")
print("Last event wins:", executions[-1] if executions else "none")
