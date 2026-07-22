"""Divan Clients — Court client factory.

CourtType enum'a göre doğru client'ı oluşturur.
Dependency injection ile altyapı bileşenlerini inject eder.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..core.enums import CourtType
from ..core.interfaces import ICourtClient, ICacheBackend
from ..config import AppConfig
from ..infrastructure.rate_limiter import AsyncTokenBucket, RateLimiterRegistry
from ..infrastructure.circuit_breaker import CircuitBreaker
from .bedesten import BedestanClient
from .anayasa import AnayasaClient
from .emsal import EmsalClient
from .mevzuat import MevzuatClient
from .bddk import BddkClient
from .kvkk import KvkkClient
from .gib import GibClient
from .sigorta import SigortaClient
from .kik import KikClient
from .btk import BtkClient
from .rekabet import RekabetClient
from .sayistay import SayistayClient
from .uyusmazlik import UyusmazlikClient

logger = logging.getLogger(__name__)


class CourtClientFactory:
    """CourtType → Client eşleştirmesi yapan factory.

    Singleton pattern değil; her çağrıda yeni instance oluşturur.
    Ancak rate limiter ve circuit breaker registry üzerinden paylaşılır.

    Usage:
        factory = CourtClientFactory(config, cache)
        bedesten = factory.create(CourtType.YARGITAY)
        all_clients = factory.create_all()
    """

    def __init__(
        self,
        config: AppConfig,
        cache: Optional[ICacheBackend] = None,
    ) -> None:
        self._config = config
        self._cache = cache
        self._rate_registry = RateLimiterRegistry()
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._clients: dict[str, ICourtClient] = {}

    def _get_rate_limiter(self, name: str) -> AsyncTokenBucket:
        """Endpoint grubuna özel rate limiter getir veya oluştur."""
        config_map = {
            "bedesten": self._config.bedesten_rate,
            "emsal": self._config.emsal_rate,
        }
        rate_config = config_map.get(name, self._config.default_rate)
        return self._rate_registry.get_or_create(name, rate_config)

    def _get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Endpoint grubuna özel circuit breaker getir veya oluştur."""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker.from_config(
                name=name, config=self._config.circuit_breaker
            )
        return self._circuit_breakers[name]

    def create(self, court_type: CourtType) -> ICourtClient:
        """Tek bir court client oluştur.

        Args:
            court_type: İstenen mahkeme türü.

        Returns:
            İlgili ICourtClient implementasyonu.

        Raises:
            ValueError: Desteklenmeyen CourtType.
        """
        # Bedesten 5 mahkemeyi kapsar
        bedesten_courts = {
            CourtType.YARGITAY,
            CourtType.DANISTAY,
            CourtType.YEREL_HUKUK,
            CourtType.ISTINAF_HUKUK,
            CourtType.KYB,
        }

        if court_type in bedesten_courts:
            key = "bedesten"
            if key not in self._clients:
                self._clients[key] = BedestanClient(
                    config=self._config,
                    rate_limiter=self._get_rate_limiter("bedesten"),
                    circuit_breaker=self._get_circuit_breaker("bedesten"),
                    cache=self._cache,
                )
            return self._clients[key]

        if court_type in (CourtType.ANAYASA_NORM, CourtType.ANAYASA_BIREYSEL):
            key = "anayasa"
            if key not in self._clients:
                self._clients[key] = AnayasaClient(
                    config=self._config,
                    rate_limiter=self._get_rate_limiter("anayasa"),
                    circuit_breaker=self._get_circuit_breaker("anayasa"),
                    cache=self._cache,
                )
            return self._clients[key]

        if court_type == CourtType.EMSAL:
            key = "emsal"
            if key not in self._clients:
                self._clients[key] = EmsalClient(
                    config=self._config,
                    rate_limiter=self._get_rate_limiter("emsal"),
                    circuit_breaker=self._get_circuit_breaker("emsal"),
                    cache=self._cache,
                )
            return self._clients[key]

        if court_type == CourtType.MEVZUAT:
            key = "mevzuat"
            if key not in self._clients:
                self._clients[key] = MevzuatClient(
                    config=self._config,
                    rate_limiter=self._get_rate_limiter("mevzuat"),
                    circuit_breaker=self._get_circuit_breaker("mevzuat"),
                    cache=self._cache,
                )
            return self._clients[key]

        client_classes = {
            CourtType.BDDK: BddkClient,
            CourtType.KVKK: KvkkClient,
            CourtType.GIB: GibClient,
            CourtType.SIGORTA_TAHKIM: SigortaClient,
            CourtType.KIK: KikClient,
            CourtType.BTK: BtkClient,
            CourtType.REKABET: RekabetClient,
            CourtType.SAYISTAY: SayistayClient,
            CourtType.UYUSMAZLIK: UyusmazlikClient,
        }

        if court_type in client_classes:
            key = court_type.name.lower()
            if key not in self._clients:
                self._clients[key] = client_classes[court_type](
                    config=self._config,
                    rate_limiter=self._get_rate_limiter(key),
                    circuit_breaker=self._get_circuit_breaker(key),
                    cache=self._cache,
                )
            return self._clients[key]

        raise ValueError(
            f"Desteklenmeyen CourtType: {court_type}. "
            f"Desteklenenler: enum değerleri."
        )

    def create_all(self) -> dict[str, ICourtClient]:
        """Tüm desteklenen client'ları oluştur.

        Returns:
            {'bedesten': BedestanClient, 'anayasa': AnayasaClient, 'emsal': EmsalClient}
        """
        self.create(CourtType.YARGITAY)    # bedesten
        self.create(CourtType.ANAYASA_NORM)  # anayasa
        self.create(CourtType.EMSAL)          # emsal
        self.create(CourtType.MEVZUAT)        # mevzuat
        self.create(CourtType.BDDK)
        self.create(CourtType.KVKK)
        self.create(CourtType.GIB)
        self.create(CourtType.SIGORTA_TAHKIM)
        self.create(CourtType.KIK)
        self.create(CourtType.BTK)
        self.create(CourtType.REKABET)
        self.create(CourtType.SAYISTAY)
        self.create(CourtType.UYUSMAZLIK)

        logger.info(f"Created {len(self._clients)} court clients: {list(self._clients.keys())}")
        return dict(self._clients)

    async def close_all(self) -> None:
        """Tüm client'ları kapat."""
        for name, client in self._clients.items():
            try:
                await client.close()
                logger.debug(f"Closed client: {name}")
            except Exception as e:
                logger.warning(f"Error closing client {name}: {e}")
        self._clients.clear()
