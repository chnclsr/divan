"""Sigorta Tahkim Komisyonu Client for Divan."""

from typing import Optional
import re
from divan.core.models import Decision, CourtType
from divan.core.enums import DecisionType
from divan.clients.base_scraper import BaseScraperClient


class SigortaClient(BaseScraperClient):
    """Sigorta Tahkim Komisyonu Kararları araması yapan istemci."""

    @property
    def search_engine_type(self) -> str:
        return "tavily"

    @property
    def search_domain(self) -> str:
        return "sigortatahkim.org"

    @property
    def court_type(self) -> CourtType:
        return CourtType.SIGORTA_TAHKIM

    def _build_search_query(self, user_query: str) -> str:
        return user_query

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        # Extract filename from url
        match = re.search(r'/([^/]+\.pdf)$', url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _parse_search_result(self, raw_result: dict, decision_id: str) -> Decision:
        return Decision(
            id=decision_id,
            court_type=CourtType.SIGORTA_TAHKIM,
            decision_type=DecisionType.KARAR,
            title=raw_result.get("title", "").replace("[PDF]", "").strip(),
            summary=raw_result.get("content", "")[:500],
            raw_metadata=raw_result
        )

    def _get_document_url(self, document_id: str) -> str:
        return f"https://www.sigortatahkim.org/content/CmsFiles/{document_id}"
