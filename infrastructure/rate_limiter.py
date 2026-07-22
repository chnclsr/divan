"""Divan Infrastructure — Generic async rate limiter.

yargi-mcp'de _TokenBucket sınıfı bedesten_mcp_module/client.py ve
emsal_mcp_module/client.py'de birebir kopyalanmıştı. Divan'da
TEK bir generic sınıf var; tüm client'lar bunu kullanır.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from ..core.exceptions import RateLimitError
from ..config import RateLimitConfig

logger = logging.getLogger(__name__)


class AsyncTokenBucket:
    """Thread-safe, asyncio uyumlu token bucket rate limiter.

    Burst kapasitesi, sabit refill hızı ve configurable max_wait ile
    hem kendi kendini düzenler hem de upstream 429'lara ``penalize``
    ile tepki verir.

    Args:
        capacity: Maksimum token sayısı (burst boyutu).
        refill_per_second: Saniyede eklenen token sayısı.
        max_wait: acquire() çağrısında maksimum bekleme süresi.
                  Aşılırsa RateLimitError fırlatılır.
    """

    def __init__(
        self,
        capacity: int = 1,
        refill_per_second: float = 0.286,  # 1 token / 3.5s
        max_wait: float = 8.0,
    ) -> None:
        self._capacity = float(capacity)
        self._refill_rate = float(refill_per_second)
        self._max_wait = max_wait
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._penalty_until = 0.0
        self._lock = asyncio.Lock()

    @classmethod
    def from_config(cls, config: RateLimitConfig) -> AsyncTokenBucket:
        """RateLimitConfig'den oluştur."""
        return cls(
            capacity=config.capacity,
            refill_per_second=1.0 / config.refill_seconds,
            max_wait=config.max_wait_seconds,
        )

    async def acquire(self, max_wait: Optional[float] = None) -> None:
        """Bir token al. Yetersizse bekle veya RateLimitError fırlat.

        Args:
            max_wait: Bu çağrıya özel maks. bekleme süresi. None ise
                      instance'ın varsayılanı kullanılır.

        Raises:
            RateLimitError: Bekleme süresi max_wait'i aşarsa.
        """
        effective_max_wait = max_wait if max_wait is not None else self._max_wait
        deadline = time.monotonic() + effective_max_wait

        while True:
            async with self._lock:
                now = time.monotonic()

                # Penalty kontrolü (upstream 429 sonrası)
                if now < self._penalty_until:
                    wait_needed = self._penalty_until - now
                else:
                    # Token'ları yenile
                    elapsed = now - self._last_refill
                    self._tokens = min(
                        self._capacity,
                        self._tokens + elapsed * self._refill_rate,
                    )
                    self._last_refill = now

                    # Token varsa kullan
                    if self._tokens >= 1.0:
                        self._tokens -= 1.0
                        return

                    # Token yoksa bekleme süresini hesapla
                    wait_needed = (1.0 - self._tokens) / self._refill_rate

            # Deadline kontrolü
            remaining = deadline - time.monotonic()
            if wait_needed > remaining:
                raise RateLimitError(
                    retry_after=wait_needed,
                    message=f"Rate limit: {wait_needed:.1f}s bekleme gerekiyor, izin verilen: {remaining:.1f}s",
                )

            await asyncio.sleep(min(wait_needed, remaining))

    def penalize(self, seconds: float) -> None:
        """Upstream 429 sonrası bucket'ı geçici olarak dondur.

        Args:
            seconds: Dondurma süresi. 1-60 saniye arasında sınırlanır.
        """
        clamped = max(1.0, min(seconds, 60.0))
        new_deadline = time.monotonic() + clamped
        self._penalty_until = max(self._penalty_until, new_deadline)
        self._tokens = 0.0
        self._last_refill = time.monotonic()
        logger.warning(f"Rate limiter paused for {clamped:.1f}s")

    @property
    def available_tokens(self) -> float:
        """Mevcut token sayısı (yaklaşık, lock alınmadan)."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        return min(self._capacity, self._tokens + elapsed * self._refill_rate)


class RateLimiterRegistry:
    """Endpoint bazında rate limiter yöneten singleton registry.

    Her endpoint grubu (bedesten, emsal, vb.) kendi bucket'ına sahiptir.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, AsyncTokenBucket] = {}

    def get_or_create(
        self,
        name: str,
        config: Optional[RateLimitConfig] = None,
    ) -> AsyncTokenBucket:
        """Adına göre bucket getir, yoksa oluştur.

        Args:
            name: Endpoint grubu adı (örn: 'bedesten', 'emsal').
            config: İlk oluşturma için yapılandırma. None ise varsayılan.
        """
        if name not in self._buckets:
            if config:
                self._buckets[name] = AsyncTokenBucket.from_config(config)
            else:
                self._buckets[name] = AsyncTokenBucket()
            logger.info(f"Rate limiter created for '{name}'")
        return self._buckets[name]

    def get(self, name: str) -> Optional[AsyncTokenBucket]:
        """Var olan bucket'ı getir, yoksa None."""
        return self._buckets.get(name)

    @property
    def all_limiters(self) -> dict[str, AsyncTokenBucket]:
        """Tüm kayıtlı limiter'lar."""
        return dict(self._buckets)
