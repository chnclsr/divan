"""Base Scraper Client for Divan.

Abstracts the logic for querying search engines (Tavily/Brave) and 
scraping individual court websites for decisions.
"""

from typing import Optional
import asyncio
from abc import abstractmethod

from divan.core.models import Decision, SearchQuery, SearchResult, HealthStatus, CourtType
from divan.core.enums import DecisionType
from divan.clients.base import BaseCourtClient
from markitdown import MarkItDown

import logging

logger = logging.getLogger(__name__)


class BaseScraperClient(BaseCourtClient):
    """Arama motoru (Tavily/Brave) üzerinden arama yapıp, sonucu kazıyan temel sınıf."""

    @classmethod
    def _get_base_url(cls) -> str:
        return ""

    @property
    def supported_courts(self) -> set[CourtType]:
        return {self.court_type}

    @property
    @abstractmethod
    def search_engine_type(self) -> str:
        """'tavily' veya 'brave' döner."""
        pass

    @property
    @abstractmethod
    def search_domain(self) -> str:
        """Arama yapılacak alan adı (Örn: kvkk.gov.tr)"""
        pass

    async def _do_search(self, query: SearchQuery) -> SearchResult:
        try:
            return await self._execute_search(query)
        except Exception as e:
            logger.error(f"{self.court_type.name} arama hatası: {e}")
            raise

    async def _execute_search(self, query: SearchQuery) -> SearchResult:
        if self.search_engine_type == "tavily":
            return await self._search_tavily(query)
        elif self.search_engine_type == "brave":
            return await self._search_brave(query)
        else:
            raise ValueError(f"Bilinmeyen search_engine_type: {self.search_engine_type}")

    @abstractmethod
    def _extract_id_from_url(self, url: str) -> Optional[str]:
        """Arama sonucundaki URL'den belge ID'sini çıkarır."""
        pass

    @abstractmethod
    def _parse_search_result(self, raw_result: dict, decision_id: str) -> Decision:
        """Arama sonucunu Decision objesine dönüştürür."""
        pass

    async def _search_tavily(self, query: SearchQuery) -> SearchResult:
        tavily_url = "https://api.tavily.com/search"
        api_key = self.config.tavily_api_key or "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"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Build search query specific to court implementation
        court_query = self._build_search_query(query.query)
        
        payload = {
            "query": court_query,
            "country": "turkey",
            "include_domains": [self.search_domain],
            "max_results": query.page_size,
            "search_depth": "advanced"
        }

        response = await self.http_client.post(tavily_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        decisions = []
        for result in data.get("results", []):
            url = result.get("url", "")
            doc_id = self._extract_id_from_url(url)
            if doc_id:
                decision = self._parse_search_result(result, doc_id)
                decision.source_url = url
                decisions.append(decision)

        return SearchResult(
            decisions=decisions,
            total_records=len(data.get("results", [])),
            page=query.page,
            page_size=query.page_size,
            courts_searched=[self.court_type]
        )

    async def _search_brave(self, query: SearchQuery) -> SearchResult:
        brave_url = "https://api.search.brave.com/res/v1/web/search"
        api_key = self.config.brave_api_token or "BSAuaRKB-dvSDSQxIN0ft1p2k6N82Kq"
        
        offset = (query.page - 1) * query.page_size
        court_query = self._build_search_query(query.query)
        
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "x-subscription-token": api_key
        }
        params = {
            "q": court_query,
            "country": "TR",
            "search_lang": "tr",
            "ui_lang": "tr-TR",
            "offset": offset,
            "count": query.page_size
        }

        response = await self.http_client.get(brave_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        decisions = []
        web_results = data.get("web", {}).get("results", [])
        
        for result in web_results:
            url = result.get("url", "")
            doc_id = self._extract_id_from_url(url)
            if doc_id:
                decision = self._parse_search_result(result, doc_id)
                decision.source_url = url
                decisions.append(decision)
                
        total = data.get("query", {}).get("total_results", len(decisions))

        return SearchResult(
            decisions=decisions,
            total_records=total,
            page=query.page,
            page_size=query.page_size,
            courts_searched=[self.court_type]
        )

    @abstractmethod
    def _build_search_query(self, user_query: str) -> str:
        """Kullanıcı sorgusunu siteye özel hale getirir."""
        pass

    @abstractmethod
    def _get_document_url(self, document_id: str) -> str:
        """Belge ID'sinden indirilecek URL'yi oluşturur."""
        pass

    async def _do_get_document(self, document_id: str) -> Decision:
        """Belgeyi hedeften indirir ve markitdown ile dönüştürür."""
        url = self._get_document_url(document_id)
        
        try:
            response = await self._http.get(url, follow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "").lower()
            content_bytes = response.content
            
            if "pdf" in content_type:
                markdown_content = await self._pdf_to_markdown(content_bytes)
            else:
                markdown_content = await self._html_to_markdown(response.text)
                
            return Decision(
                id=document_id,
                court_type=self.court_type,
                markdown_content=markdown_content,
                source_url=url,
                raw_metadata={}
            )
            
        except Exception as e:
            logger.error(f"Belge içeriği getirme hatası ({url}): {e}")
            raise
