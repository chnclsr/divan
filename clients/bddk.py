"""BDDK (Bankacılık Düzenleme ve Denetleme Kurumu) Client for Divan."""

from typing import Optional
import re
from divan.core.models import Decision, CourtType
from divan.core.enums import DecisionType
from divan.clients.base_scraper import BaseScraperClient


class BddkClient(BaseScraperClient):
    """BDDK Kurul Kararları araması yapan istemci."""

    @property
    def search_engine_type(self) -> str:
        return "tavily"

    @property
    def search_domain(self) -> str:
        return "https://www.bddk.org.tr/Mevzuat/DokumanGetir"

    @property
    def court_type(self) -> CourtType:
        return CourtType.BDDK

    def _build_search_query(self, user_query: str) -> str:
        return f"{user_query} \"Karar Sayısı\""

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        match = re.search(r'/DokumanGetir/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'/Liste/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'ekId=(\d+)', url)
        if match:
            return match.group(1)
        return None

    def _parse_search_result(self, raw_result: dict, decision_id: str) -> Decision:
        return Decision(
            id=decision_id,
            court_type=CourtType.BDDK,
            decision_type=DecisionType.KURUL_KARARI,
            title=raw_result.get("title", "").replace("[PDF]", "").strip(),
            summary=raw_result.get("content", "")[:500],
            raw_metadata=raw_result
        )

    def _get_document_url(self, document_id: str) -> str:
        return f"https://www.bddk.org.tr/Mevzuat/DokumanGetir/{document_id}"
