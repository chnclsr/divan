"""Divan Services — Document retrieval service."""

from __future__ import annotations

import logging
from typing import Optional

from ..core.enums import CourtType
from ..core.interfaces import IDocumentService
from ..core.models import Decision
from ..clients.factory import CourtClientFactory

logger = logging.getLogger(__name__)


class DocumentService(IDocumentService):
    """Belge getirme ve işleme servisi.

    Client factory üzerinden doğru client'ı bulur,
    belgeyi getirir ve Decision modeline normalize eder.
    """

    def __init__(self, factory: CourtClientFactory) -> None:
        self._factory = factory

    async def get_document(self, document_id: str, court_type: CourtType) -> Decision:
        """Belge getir ve Markdown'a çevir.

        Args:
            document_id: Belge ID'si (kaynak sisteme özgü).
            court_type: Hangi mahkeme/kurum.

        Returns:
            Markdown içerikli Decision.
        """
        client = self._factory.create(court_type)
        decision = await client.get_document(document_id)
        logger.info(
            f"Document fetched: {decision.id} from {court_type.name} "
            f"({len(decision.markdown_content or '')} chars)"
        )
        return decision
