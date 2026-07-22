"""Divan Infrastructure — Resilient async HTTP client.

yargi-mcp'deki her client kendi httpx.AsyncClient'ını oluşturuyordu,
her birinde farklı header'lar, timeout'lar ve hata yönetimi vardı.
Divan'da TEK bir resilient HTTP client var; retry, backoff, circuit breaker
ve rate limiter entegrasyonu built-in.
"""

from __future__ import annotations

import asyncio
import logging
import random
import ssl
from typing import Any, Optional

import httpx

from ..core.exceptions import (
    ClientError,
    EndpointUnavailableError,
    RateLimitError,
)
from ..config import AppConfig
from .rate_limiter import AsyncTokenBucket
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class ResilientHttpClient:
    """Production-grade async HTTP client with built-in resilience.

    Features:
        - Exponential backoff with jitter
        - Configurable retry count and status codes
        - Circuit breaker integration
        - Rate limiter integration
        - Custom SSL context support (KİK gibi eski sunucular için)
        - Structured logging

    Args:
        base_url: API'nin temel URL'i.
        headers: Varsayılan HTTP header'lar.
        timeout: İstek timeout'u (saniye).
        max_retries: Maks. yeniden deneme sayısı.
        backoff_base: Exponential backoff tabanı (saniye).
        backoff_max: Maks. backoff süresi (saniye).
        rate_limiter: İsteğe bağlı token bucket.
        circuit_breaker: İsteğe bağlı circuit breaker.
        verify_ssl: SSL doğrulaması. False veya ssl.SSLContext geçilebilir.
        retryable_status_codes: Yeniden denenecek HTTP durum kodları.
    """

    # Varsayılan olarak retry edilecek HTTP kodları
    DEFAULT_RETRYABLE_CODES = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        base_url: str,
        headers: Optional[dict[str, str]] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_max: float = 30.0,
        rate_limiter: Optional[AsyncTokenBucket] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        verify_ssl: bool | ssl.SSLContext = True,
        retryable_status_codes: Optional[frozenset[int]] = None,
    ) -> None:
        self.base_url = base_url
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._rate_limiter = rate_limiter
        self._circuit_breaker = circuit_breaker
        self._retryable_codes = retryable_status_codes or self.DEFAULT_RETRYABLE_CODES

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers or {},
            timeout=timeout,
            verify=verify_ssl,
            follow_redirects=True,
        )

    # ── Public API ────────────────────────────────────────────────────────

    async def get(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """Resilient GET isteği."""
        return await self._request("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        *,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """Resilient POST isteği."""
        return await self._request("POST", path, json=json, data=data, headers=headers)

    async def close(self) -> None:
        """HTTP client'ı kapat."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug(f"HTTP client closed for {self.base_url}")

    # ── Internal ──────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """Retry + backoff + circuit breaker + rate limiter ile istek at."""
        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            try:
                # Circuit breaker kontrolü
                if self._circuit_breaker:
                    await self._circuit_breaker.before_call()

                # Rate limiter kontrolü
                if self._rate_limiter:
                    await self._rate_limiter.acquire()

                # İstek at
                response = await self._client.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    data=data,
                    headers=headers,
                )

                # 429 handling
                if response.status_code == 429:
                    retry_after = self._parse_retry_after(response)
                    if self._rate_limiter:
                        self._rate_limiter.penalize(retry_after)
                    if self._circuit_breaker:
                        await self._circuit_breaker.on_failure(
                            Exception(f"HTTP 429 from {self.base_url}{path}")
                        )
                    if attempt < self._max_retries:
                        logger.warning(
                            f"HTTP 429 on {method} {path} (attempt {attempt + 1}), "
                            f"retrying in {retry_after:.1f}s"
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    raise RateLimitError(
                        retry_after=retry_after,
                        message=f"Rate limit aşıldı: {self.base_url}{path}",
                    )

                # Retryable status code kontrolü
                if response.status_code in self._retryable_codes and attempt < self._max_retries:
                    wait = self._calculate_backoff(attempt)
                    logger.warning(
                        f"HTTP {response.status_code} on {method} {path} "
                        f"(attempt {attempt + 1}), retrying in {wait:.1f}s"
                    )
                    if self._circuit_breaker:
                        await self._circuit_breaker.on_failure(
                            Exception(f"HTTP {response.status_code}")
                        )
                    await asyncio.sleep(wait)
                    continue

                # Başarı
                response.raise_for_status()
                if self._circuit_breaker:
                    await self._circuit_breaker.on_success()

                return response

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_error = e
                if self._circuit_breaker:
                    await self._circuit_breaker.on_failure(e)
                if attempt < self._max_retries:
                    wait = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Connection error on {method} {path} "
                        f"(attempt {attempt + 1}): {e}, retrying in {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
                    continue
                raise EndpointUnavailableError(
                    f"Sunucu erişilemez: {self.base_url}{path}",
                    cause=e,
                ) from e

            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as e:
                last_error = e
                if self._circuit_breaker:
                    await self._circuit_breaker.on_failure(e)
                if attempt < self._max_retries:
                    wait = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Timeout on {method} {path} "
                        f"(attempt {attempt + 1}): {e}, retrying in {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
                    continue
                raise EndpointUnavailableError(
                    f"İstek zaman aşımı: {self.base_url}{path}",
                    cause=e,
                ) from e

            except httpx.HTTPStatusError as e:
                if self._circuit_breaker:
                    await self._circuit_breaker.on_failure(e)
                raise ClientError(
                    f"HTTP {e.response.status_code}: {self.base_url}{path}",
                    cause=e,
                ) from e

            except RateLimitError:
                raise  # Zaten handle edildi, yukarı fırlat

            except Exception as e:
                last_error = e
                if self._circuit_breaker:
                    await self._circuit_breaker.on_failure(e)
                raise ClientError(
                    f"Beklenmeyen hata: {self.base_url}{path}: {e}",
                    cause=e,
                ) from e

        # Tüm denemeler tükendi
        raise EndpointUnavailableError(
            f"Tüm denemeler tükendi ({self._max_retries + 1}x): {self.base_url}",
            cause=last_error,
        )

    def _calculate_backoff(self, attempt: int) -> float:
        """Exponential backoff with full jitter (AWS recommended)."""
        exp_delay = self._backoff_base * (2 ** attempt)
        capped_delay = min(exp_delay, self._backoff_max)
        return random.uniform(0, capped_delay)

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float:
        """Retry-After header'ını parse et. Yoksa 30s varsayılan."""
        raw = response.headers.get("Retry-After", "")
        try:
            value = float(raw)
            return max(1.0, min(value, 60.0))
        except (TypeError, ValueError):
            return 30.0

    # ── Context Manager ───────────────────────────────────────────────────

    async def __aenter__(self) -> ResilientHttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


def create_legacy_ssl_context() -> ssl.SSLContext:
    """KİK gibi eski TLS sunucuları için gevşetilmiş SSL context.

    yargi-mcp'deki kik_mcp_module/client_v2.py'den alınmış.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
    ctx.set_ciphers("ALL:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA")
    return ctx
