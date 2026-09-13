"""Validación de solicitudes y límite global de vinculación para la red local."""
import threading
import time
from collections import deque
from collections.abc import Callable


class RequestError(ValueError):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class PairingLimiter:
    """Ventana global acotada: cambiar de IP no permite eludir el límite."""
    def __init__(self, attempts: int = 5, seconds: float = 60,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.attempts = attempts
        self.seconds = seconds
        self.clock = clock
        self._times = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            now = self.clock()
            while self._times and self._times[0] <= now - self.seconds:
                self._times.popleft()
            if len(self._times) >= self.attempts:
                return False
            self._times.append(now)
            return True
