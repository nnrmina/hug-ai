"""Short-term conversation memory (last few turns per session).

In-memory with TTL — fine for a single server. On serverless (Vercel) each instance has its
own memory, so the client also sends its recent turns and those are used when the server
copy is missing. For multi-instance production, back this with Redis.
"""
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from app.core.config import settings


class SessionStore:
    def __init__(
        self,
        ttl_s: Optional[int] = None,
        max_turns: Optional[int] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl_s = ttl_s or settings.SESSION_TTL_S
        self.max_turns = max_turns or settings.SESSION_MAX_TURNS
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: Dict[str, Tuple[float, Deque[Dict[str, Any]]]] = {}

    def _purge(self, now: float) -> None:
        expired = [sid for sid, (exp, _) in self._sessions.items() if exp <= now]
        for sid in expired:
            del self._sessions[sid]

    def get(self, session_id: Optional[str]) -> List[Dict[str, Any]]:
        if not session_id:
            return []
        with self._lock:
            now = self._clock()
            self._purge(now)
            entry = self._sessions.get(session_id)
            return list(entry[1]) if entry else []

    def append(self, session_id: Optional[str], turn: Dict[str, Any]) -> None:
        if not session_id:
            return
        with self._lock:
            now = self._clock()
            self._purge(now)
            _, turns = self._sessions.get(session_id, (0.0, deque(maxlen=self.max_turns)))
            turns.append(turn)
            self._sessions[session_id] = (now + self.ttl_s, turns)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


session_store = SessionStore()
