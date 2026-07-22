"""Divan Core — Package exports."""

from .enums import CourtType, DecisionType, SearchScope, ExportFormat, CircuitState
from .exceptions import (
    DivanError,
    ClientError,
    RateLimitError,
    CircuitOpenError,
    EndpointUnavailableError,
    AuthenticationError,
    DocumentError,
    DocumentNotFoundError,
    ConversionError,
    MalformedResponseError,
    ValidationError,
)
from .models import (
    Court,
    Decision,
    DateRange,
    SearchQuery,
    SearchResult,
    HealthStatus,
)
from .interfaces import (
    ICourtClient,
    ISearchService,
    IDocumentService,
    IExporter,
    ICacheBackend,
)

__all__ = [
    # Enums
    "CourtType", "DecisionType", "SearchScope", "ExportFormat", "CircuitState",
    # Exceptions
    "DivanError", "ClientError", "RateLimitError", "CircuitOpenError",
    "EndpointUnavailableError", "AuthenticationError",
    "DocumentError", "DocumentNotFoundError", "ConversionError",
    "MalformedResponseError", "ValidationError",
    # Models
    "Court", "Decision", "DateRange", "SearchQuery", "SearchResult", "HealthStatus",
    # Interfaces
    "ICourtClient", "ISearchService", "IDocumentService", "IExporter", "ICacheBackend",
]
