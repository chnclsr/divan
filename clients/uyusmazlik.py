"""Uyuşmazlık Mahkemesi Client for Divan."""

from typing import Optional
import re
from divan.core.models import Decision, CourtType
from divan.core.enums import DecisionType
from divan.clients.base_scraper import BaseScraperClient


class UyusmazlikClient(BaseScraperClient):
    """Uyuşmazlık Mahkemesi Kararları araması yapan istemci."""

    @property
    def search_engine_type(self) -> str:
        return "brave"

    @property
    def search_domain(self) -> str:
        return "kararlar.uyusmazlik.gov.tr"

    @property
    def court_type(self) -> CourtType:
        return CourtType.UYUSMAZLIK

    def _build_search_query(self, user_query: str) -> str:
        return f"site:kararlar.uyusmazlik.gov.tr {user_query}"

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        match = re.search(r'Id=(\d+)', url, re.IGNORECASE)
        if match:
            return match.group(1)
        return "UNKNOWN_ID"

    def _parse_search_result(self, raw_result: dict, decision_id: str) -> Decision:
        return Decision(
            id=decision_id,
            court_type=CourtType.UYUSMAZLIK,
            decision_type=DecisionType.KARAR,
            title=raw_result.get("title", "").strip(),
            summary=raw_result.get("description", "")[:500],
            raw_metadata=raw_result
        )

    def _get_document_url(self, document_id: str) -> str:
        return f"https://kararlar.uyusmazlik.gov.tr/Karar/Detay?Id={document_id}"
