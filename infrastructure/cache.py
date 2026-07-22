"""Divan Infrastructure — In-memory LRU cache.

Performans için TTL'li LRU cache. SQLite yok (online-only MCP sunucusu).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

from ..core.interfaces import ICacheBackend

logger = logging.getLogger(__name__)


class _CacheEntry:
    """Tek bir cache girdisi."""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: bytes, ttl: int) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def is_expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class LRUMemoryCache(ICacheBackend):
    """Thread-safe, TTL'li, LRU eviction stratejili in-memory cache.

    Args:
        max_size: Maksimum cache girdisi sayısı.
        default_ttl: Varsayılan yaşam süresi (saniye).
    """

    def __init__(self, max_size: int = 500, default_ttl: int = 3600) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    async def get(self, key: str) -> Optional[bytes]:
        """Cache'ten değer getir. Miss veya expire ise None döner."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None

            if entry.is_expired:
                del self._store[key]
                self._stats["misses"] += 1
                return None

            # LRU: en sona taşı
            self._store.move_to_end(key)
            self._stats["hits"] += 1
            return entry.value

    async def set(self, key: str, value: bytes, ttl: int = 0) -> None:
        """Cache'e değer yaz. TTL=0 ise varsayılan kullanılır."""
        effective_ttl = ttl if ttl > 0 else self._default_ttl

        async with self._lock:
            # Zaten varsa güncelle
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = _CacheEntry(value, effective_ttl)
                return

            # Kapasite kontrolü — en eski (LRU) girdiyi sil
            while len(self._store) >= self._max_size:
                evicted_key, _ = self._store.popitem(last=False)
                self._stats["evictions"] += 1
                logger.debug(f"Cache eviction: {evicted_key}")

            self._store[key] = _CacheEntry(value, effective_ttl)

    async def delete(self, key: str) -> None:
        """Cache'ten girdiyi sil."""
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        """Tüm cache'i temizle."""
        async with self._lock:
            self._store.clear()
            logger.info("Cache cleared")

    @property
    def size(self) -> int:
        """Mevcut girdi sayısı."""
        return len(self._store)

    @property
    def stats(self) -> dict[str, int]:
        """Cache istatistikleri."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0
        return {**self._stats, "size": self.size, "hit_rate_pct": round(hit_rate, 1)}


class CacheKeyBuilder:
    """Deterministik cache key oluşturucu.

    Aynı parametrelerle yapılan istekler her zaman aynı key'i üretir.
    """

    @staticmethod
    def build(namespace: str, **params: Any) -> str:
        """Namespace + parametrelerden SHA-256 tabanlı cache key oluştur.

        Args:
            namespace: İzolasyon alanı (örn: 'bedesten:search', 'emsal:document').
            **params: Anahtar-değer çiftleri.

        Returns:
            'namespace:sha256_hash' formatında key.
        """
        # Parametreleri sıralı JSON'a çevir (deterministic)
        sorted_params = json.dumps(params, sort_keys=True, ensure_ascii=False)
        hash_digest = hashlib.sha256(sorted_params.encode("utf-8")).hexdigest()[:16]
        return f"{namespace}:{hash_digest}"
