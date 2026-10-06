"""Limiteur de débit en mémoire (fenêtre glissante), sans dépendance.

Limite : l'état est propre à chaque processus. Avec N workers Gunicorn la limite
effective est N × max_calls ; pour une limite globale, utiliser Redis (Flask-Limiter).
"""
import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_calls, window_seconds):
        self.max_calls = max_calls
        self.window = window_seconds
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key, now=None):
        """Retourne (autorisé, secondes_avant_nouvel_essai)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.max_calls:
                return False, max(1, int(self.window - (now - q[0])) + 1)
            q.append(now)
            if len(self._hits) > 10_000:  # borne mémoire : purge des clés expirées
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
                    del self._hits[k]
            return True, 0
