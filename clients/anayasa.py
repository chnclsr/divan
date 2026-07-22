"""Divan Clients — Anayasa Mahkemesi (AYM) client.

KBB JSON API üzerinden norm denetimi ve bireysel başvuru kararlarına erişim.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Optional

from ..core.enums import CourtType, DecisionType
from ..core.models import Decision, SearchQuery, SearchResult
from ..core.exceptions import DocumentNotFoundError
from .base import BaseCourtClient

logger = logging.getLogger(__name__)

# AYM Karar Tipi Sabitleri
KARAR_TIPI_NORM = "NormDenetimi"
KARAR_TIPI_BIREYSEL = "BireyselBasvuru"
DOCUMENT_CHUNK_SIZE = 5000


class AnayasaClient(BaseCourtClient):
    """Anayasa Mahkemesi Kararlar Bilgi Bankası (KBB) client.

    Endpoint: https://kararlarbilgibankasi.anayasa.gov.tr
    Kapsam: Norm Denetimi + Bireysel Başvuru
    Protokol: REST JSON (GET/POST)
    """

    SEARCH_ENDPOINT = "/api/core/public/search"
    DETAIL_ENDPOINT = "/api/core/public/search"

    @property
    def court_type(self) -> CourtType:
        return CourtType.ANAYASA_NORM

    @property
    def supported_courts(self) -> list[CourtType]:
        return [CourtType.ANAYASA_NORM, CourtType.ANAYASA_BIREYSEL]

    @classmethod
    def _get_base_url(cls) -> str:
        return "https://kararlarbilgibankasi.anayasa.gov.tr"

    @classmethod
    def _get_default_headers(cls) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": "https://kararlarbilgibankasi.anayasa.gov.tr",
            "Referer": "https://kararlarbilgibankasi.anayasa.gov.tr/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
        }

    @classmethod
    def _get_ssl_verify(cls) -> bool:
        return True

    # ── Search ────────────────────────────────────────────────────────────

    async def _do_search(self, query: SearchQuery) -> SearchResult:
        """AYM KBB API'de arama yap."""
        karar_tipi = KARAR_TIPI_NORM
        for court in query.courts:
            if court == CourtType.ANAYASA_BIREYSEL:
                karar_tipi = KARAR_TIPI_BIREYSEL
                break

        payload = {
            "kararTipi": karar_tipi,
            "page": query.page,
            "size": query.page_size,
        }
        if query.query:
            payload["query"] = query.query

        logger.info(f"AYM search: query='{query.query}', type={karar_tipi}, page={query.page}")
        response = await self._http.post(self.SEARCH_ENDPOINT, json=payload)
        data = response.json()

        return self._parse_search_response(data, query, karar_tipi)

    def _parse_search_response(
        self, payload: dict[str, Any], query: SearchQuery, karar_tipi: str
    ) -> SearchResult:
        """AYM API yanıtını unified SearchResult'a dönüştür."""
        total = int(payload.get("total", 0))
        raw_items = payload.get("data", [])

        decisions: list[Decision] = []
        for item in raw_items:
            decisions.append(self._raw_to_decision(item, karar_tipi))

        total_pages = (total + query.page_size - 1) // query.page_size if total > 0 else 0

        return SearchResult(
            decisions=decisions,
            total_records=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
            courts_searched=query.courts,
        )

    def _raw_to_decision(self, item: dict[str, Any], karar_tipi: str) -> Decision:
        """Ham AYM yanıtını Decision modeline normalize et."""
        esas_no = item.get("esasNo", "")
        karar_no = item.get("kararNo", "")
        reference = ""
        if esas_no and karar_no:
            reference = f"E.{esas_no}, K.{karar_no}"

        court_type = (
            CourtType.ANAYASA_BIREYSEL
            if karar_tipi == KARAR_TIPI_BIREYSEL
            else CourtType.ANAYASA_NORM
        )

        decision_type = (
            DecisionType.BIREYSEL_BASVURU
            if karar_tipi == KARAR_TIPI_BIREYSEL
            else DecisionType.NORM_DENETIMI
        )

        item_id = str(item.get("id", ""))
        doc_url = self._build_document_url(karar_tipi, item_id)

        return Decision(
            id=item_id,
            court_type=court_type,
            decision_type=decision_type,
            esas_no=f"E.{esas_no}" if esas_no else None,
            karar_no=f"K.{karar_no}" if karar_no else None,
            chamber_name="Anayasa Mahkemesi",
            decision_date_str=item.get("kararTarihi", ""),
            title=self._strip_html(item.get("kararKonusu", "")),
            summary=item.get("basvuruTuruLabel", ""),
            source_url=doc_url,
            document_url=doc_url,
            raw_metadata=item,
        )

    # ── Document ──────────────────────────────────────────────────────────

    async def _do_get_document(self, document_id: str) -> Decision:
        """AYM kararının tam metnini getir."""
        # document_id URL veya UUID olabilir
        karar_tipi, uuid = self._parse_document_url(document_id)
        if karar_tipi is None:
            karar_tipi = KARAR_TIPI_NORM
        if not uuid:
            uuid = document_id

        endpoint = self.DETAIL_ENDPOINT
        payload = {
            "kararTipi": karar_tipi,
            "id": uuid,
            "page": 1,
            "size": 1
        }

        logger.info(f"AYM document fetch: UUID={uuid}, type={karar_tipi}")
        response = await self._http.post(endpoint, json=payload)
        data = response.json()
        
        records = data.get("data", [])
        record = records[0] if records else {}

        if not record:
            print("AYM API RESPONSE FOR DOC:", data)
            raise DocumentNotFoundError(document_id)

        # İçeriği Markdown'a çevir
        icerik = record.get("icerik", "")
        markdown = await self._html_to_markdown(icerik) if icerik else ""

        esas_no = record.get("esasNo", "")
        karar_no = record.get("kararNo", "")

        court_type = (
            CourtType.ANAYASA_BIREYSEL
            if karar_tipi == KARAR_TIPI_BIREYSEL
            else CourtType.ANAYASA_NORM
        )

        return Decision(
            id=uuid,
            court_type=court_type,
            esas_no=f"E.{esas_no}" if esas_no else None,
            karar_no=f"K.{karar_no}" if karar_no else None,
            chamber_name="Anayasa Mahkemesi",
            decision_date_str=record.get("kararTarihi", ""),
            markdown_content=markdown,
            source_url=self._build_document_url(karar_tipi, uuid),
            raw_metadata=record,
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _build_document_url(karar_tipi: str, uuid: str) -> str:
        prefix = "BB" if karar_tipi == KARAR_TIPI_BIREYSEL else "ND"
        return f"https://kararlarbilgibankasi.anayasa.gov.tr/{prefix}/{uuid}"

    @staticmethod
    def _parse_document_url(url: str) -> tuple[Optional[str], str]:
        """URL'den karar tipini ve UUID'yi ayıkla."""
        if "/BB/" in url:
            return KARAR_TIPI_BIREYSEL, url.split("/BB/")[-1]
        if "/ND/" in url:
            return KARAR_TIPI_NORM, url.split("/ND/")[-1]
        return None, url

    @staticmethod
    def _strip_html(text: Optional[str]) -> str:
        if not text:
            return ""
        return re.sub(r"<[^>]+>", "", text).strip()
