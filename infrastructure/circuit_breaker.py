"""Divan Infrastructure — Circuit Breaker pattern.

ABD'deki enterprise hukuk sistemlerinde (Westlaw, LexisNexis) standart
olan fail-fast mekanizması. yargi-mcp'de hiç yok.

Bir API endpoint'i ardışık olarak N kez başarısız olursa, circuit breaker
OPEN durumuna geçer ve yeni istekleri anında reddeder (sunucuyu daha
fazla yormaz). Bekleme süresi sonunda HALF_OPEN'a geçer ve tek bir
test isteği gönderir.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from ..core.enums import CircuitState
from ..core.exceptions import CircuitOpenError
from ..config import CircuitBreakerConfig

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Async-aware circuit breaker.

    States:
        CLOSED    → Normal çalışma. Hatalar sayılır.
        OPEN      → failure_threshold aşıldı. Tüm istekler engellenir.
        HALF_OPEN → recovery_timeout doldu. Sınırlı test istekleri izin verilir.

    Thread Safety:
        asyncio.Lock ile korunur; aynı event loop içinde güvenlidir.

    Args:
        name: İnsan-okunur tanımlayıcı (loglarda görünür).
        failure_threshold: OPEN'a geçmek için gerekli ardışık hata sayısı.
        recovery_timeout: OPEN→HALF_OPEN bekleme süresi (saniye).
        half_open_max_calls: HALF_OPEN'da izin verilen maks. eşzamanlı istek.
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @classmethod
    def from_config(cls, name: str, config: CircuitBreakerConfig) -> CircuitBreaker:
        """CircuitBreakerConfig'den oluştur."""
        return cls(
            name=name,
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout,
            half_open_max_calls=config.half_open_max_calls,
        )

    @property
    def state(self) -> CircuitState:
        """Mevcut durum (otomatik OPEN→HALF_OPEN geçişi dahil)."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    async def before_call(self) -> None:
        """İstek öncesi kontrol. OPEN ise CircuitOpenError fırlatır.

        Raises:
            CircuitOpenError: Devre açıksa.
        """
        async with self._lock:
            current_state = self.state

            if current_state == CircuitState.CLOSED:
                return  # İzin ver

            if current_state == CircuitState.OPEN:
                remaining = self._recovery_timeout - (
                    time.monotonic() - self._last_failure_time
                )
                raise CircuitOpenError(remaining_seconds=max(0, remaining))

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self._half_open_max_calls:
                    self._half_open_calls += 1
                    return  # Test isteğine izin ver
                remaining = self._recovery_timeout - (
                    time.monotonic() - self._last_failure_time
                )
                raise CircuitOpenError(remaining_seconds=max(0, remaining))

    async def on_success(self) -> None:
        """Başarılı istek sonrası durumu güncelle."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                # Test isteği başarılı → CLOSED'a dön
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
                logger.info(f"CircuitBreaker '{self.name}': HALF_OPEN → CLOSED (recovered)")
            elif self._state == CircuitState.CLOSED:
                # Ardışık hata sayacını sıfırla
                self._failure_count = 0

    async def on_failure(self, error: Optional[Exception] = None) -> None:
        """Başarısız istek sonrası durumu güncelle."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self.state == CircuitState.HALF_OPEN:
                # Test isteği başarısız → tekrar OPEN
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(
                    f"CircuitBreaker '{self.name}': HALF_OPEN → OPEN "
                    f"(test failed: {error})"
                )
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self._failure_threshold
            ):
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(
                    f"CircuitBreaker '{self.name}': CLOSED → OPEN "
                    f"(failures: {self._failure_count}/{self._failure_threshold})"
                )

    async def reset(self) -> None:
        """Manuel sıfırlama."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            logger.info(f"CircuitBreaker '{self.name}': manually reset to CLOSED")

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name='{self.name}', state={self.state.value}, "
            f"failures={self._failure_count}/{self._failure_threshold})"
        )
