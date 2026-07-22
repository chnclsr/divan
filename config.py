"""Divan — Uygulama konfigürasyonu.

Pydantic Settings ile ortam değişkenlerinden veya varsayılanlardan
yapılandırma yükler. Tüm bileşenler bu tek merkezi config'i kullanır.
"""

from __future__ import annotations

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class RateLimitConfig(BaseSettings):
    """Bir endpoint grubunun rate-limit ayarları."""

    capacity: int = Field(1, description="Token bucket kapasitesi")
    refill_seconds: float = Field(3.5, description="Bir token'ın yenilenme süresi (s)")
    max_wait_seconds: float = Field(8.0, description="Bucket'ta maks. bekleme süresi (s)")


class CircuitBreakerConfig(BaseSettings):
    """Circuit breaker ayarları."""

    failure_threshold: int = Field(5, description="OPEN'a geçiş için ardışık hata sayısı")
    recovery_timeout: float = Field(30.0, description="OPEN→HALF_OPEN bekleme süresi (s)")
    half_open_max_calls: int = Field(1, description="HALF_OPEN'da izin verilen istek sayısı")


class AppConfig(BaseSettings):
    """Ana uygulama konfigürasyonu.

    Ortam değişkenleri `DIVAN_` prefix'i ile override edilebilir:
        DIVAN_LOG_LEVEL=DEBUG
        DIVAN_HTTP_TIMEOUT=30
    """

    model_config = {"env_prefix": "DIVAN_", "env_nested_delimiter": "__"}

    # ── Genel ──
    log_level: str = Field("INFO", description="Loglama seviyesi")
    app_name: str = Field("Divan", description="Uygulama adı")
    version: str = Field("0.1.0", description="Sürüm")

    # ── HTTP ──
    http_timeout: float = Field(60.0, description="Varsayılan HTTP timeout (s)")
    http_max_retries: int = Field(3, description="Maks. yeniden deneme sayısı")
    http_backoff_base: float = Field(1.0, description="Exponential backoff tabanı (s)")
    http_backoff_max: float = Field(30.0, description="Maks. backoff süresi (s)")

    # ── Rate Limiting ──
    bedesten_rate: RateLimitConfig = Field(
        default_factory=lambda: RateLimitConfig(capacity=1, refill_seconds=3.5, max_wait_seconds=8.0)
    )
    emsal_rate: RateLimitConfig = Field(
        default_factory=lambda: RateLimitConfig(capacity=1, refill_seconds=3.5, max_wait_seconds=8.0)
    )
    default_rate: RateLimitConfig = Field(
        default_factory=lambda: RateLimitConfig(capacity=3, refill_seconds=1.0, max_wait_seconds=5.0)
    )

    # ── Circuit Breaker ──
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)

    # ── External Search (Legacy Scrapers) ──
    tavily_api_key: Optional[str] = Field(None, alias="TAVILY_API_KEY")
    brave_api_token: Optional[str] = Field(None, alias="BRAVE_API_TOKEN")

    # ── Cache ──
    cache_ttl: int = Field(3600, description="Varsayılan cache TTL (s)")
    cache_max_size: int = Field(500, description="LRU cache maks. girdi sayısı")

    # ── MCP Server ──
    mcp_server_name: str = Field("Divan MCP Server", description="MCP sunucu adı")
    mcp_server_version: str = Field("0.1.0", description="MCP sunucu sürümü")

    # ── FastAPI ──
    api_host: str = Field("0.0.0.0", description="API sunucu adresi")
    api_port: int = Field(8000, description="API sunucu portu")
