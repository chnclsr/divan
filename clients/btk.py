# btk_mcp_module/client.py

import asyncio
import io
import logging
import math
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from markitdown import MarkItDown
from pydantic import HttpUrl

from divan.core.models import Decision, SearchQuery, SearchResult, HealthStatus, CourtType
from divan.core.enums import DecisionType
from divan.clients.base import BaseCourtClient

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


class BtkClient(BaseCourtClient):
    """Client for BTK (Information and Communication Technologies Authority) decisions."""

    BASE_URL = "https://www.btk.tr"
    API_PATH = "/api/content/board-decisions"

    @classmethod
    def _get_base_url(cls) -> str:
        return cls.BASE_URL

    @staticmethod
    def _format_date(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).date().isoformat()
        except ValueError:
            return value[:10] if len(value) >= 10 else value

    @staticmethod
    def _extract_pdf_url(file_data: Any) -> Optional[str]:
        if not isinstance(file_data, dict):
            return None
        for key in ("url", "storageUrl"):
            value = file_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _parse_decision(self, item: Dict[str, Any]) -> Decision:
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        file_data = data.get("file_url") if isinstance(data.get("file_url"), dict) else {}
        pdf_url = self._extract_pdf_url(file_data)

        return Decision(
            id=str(item.get("id") or ""),
            court_type=CourtType.BTK,
            decision_type=DecisionType.KURUL_KARARI,
            title=str(item.get("title") or ""),
            karar_no=data.get("decision_no"),
            decision_date_str=self._format_date(data.get("decision_date")),
            source_url=pdf_url,
            raw_metadata=item
        )

    @property
    def court_type(self) -> CourtType:
        return CourtType.BTK

    @property
    def supported_courts(self) -> set[CourtType]:
        return {CourtType.BTK}

    async def _do_search(self, request: SearchQuery) -> SearchResult:
        params: Dict[str, str] = {
            "page": str(request.page),
            "limit": str(request.page_size),
            "locale": "tr",
        }

        if request.query and request.query.strip():
            params["search"] = request.query.strip()
        if request.karar_no and request.karar_no.strip():
            params["filter[decision_no]"] = request.karar_no.strip()

        query_string = urlencode(params, doseq=True)
        query_url = f"{self.BASE_URL}{self.API_PATH}?{query_string}"

        try:
            response = await self._http.get(self.API_PATH, params=params)
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            raise Exception(f"Failed to search BTK decisions: {str(e)}")

        raw_items = payload.get("data") if isinstance(payload, dict) else []
        decisions = [
            self._parse_decision(item)
            for item in raw_items
            if isinstance(item, dict)
        ]
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}

        return SearchResult(
            decisions=decisions,
            total_records=int(meta.get("total") or len(decisions)),
            page=int(meta.get("page") or request.page),
            page_size=int(meta.get("limit") or request.page_size),
            courts_searched=[CourtType.BTK],
        )

    async def _do_get_document(self, document_id: str) -> Decision:
        # BTK uses document ID to find PDF, but here we expect the user/client to provide the PDF URL inside the SearchResult.
        # Since document_id is not enough, we will re-search the ID to get the URL
        request = SearchQuery(query="", page=1, page_size=1)
        params = {"page": "1", "limit": "10"}
        response = await self.http_client.get(f"{self.API_PATH}/{document_id}")
        response.raise_for_status()
        payload = response.json()
        
        item = payload.get("data", {})
        data = item.get("data", {})
        file_data = data.get("file_url", {})
        pdf_url = self._extract_pdf_url(file_data)
        
        if not pdf_url:
            raise ValueError("No PDF URL found for BTK document")

        try:
            res = await self._http.get(pdf_url)
            res.raise_for_status()

            md = MarkItDown(enable_plugins=False)
            result = await asyncio.to_thread(md.convert_stream, res.content, file_extension=".pdf")

            return Decision(
                id=document_id,
                court_type=CourtType.BTK,
                markdown_content=result.text_content,
                source_url=pdf_url,
                raw_metadata=item
            )
        except Exception as e:
            logger.error("BtkApiClient: error retrieving BTK PDF %s: %s", pdf_url, e, exc_info=True)
            raise Exception(f"Failed to retrieve BTK document: {str(e)}")
