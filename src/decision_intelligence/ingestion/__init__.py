"""PDF ingestion — parse a document into a validated OptimizationRequest."""

from .ips import (
    PolicyFieldExtraction,
    PolicyIngestionResult,
    ingest_policy_document,
    supported_policy_workflows,
)
from .mapper import IngestionError, to_optimization_request
from .pdf_ingest import (
    extract_heuristic,
    extract_text,
    extract_with_llm,
    ingest_pdf,
    llm_available,
)
from .schema import ExtractedConstraint, ExtractedRequest, ExtractedScenario

__all__ = [
    "IngestionError",
    "PolicyFieldExtraction",
    "PolicyIngestionResult",
    "ingest_policy_document",
    "supported_policy_workflows",
    "to_optimization_request",
    "ingest_pdf",
    "llm_available",
    "extract_heuristic",
    "extract_with_llm",
    "extract_text",
    "ExtractedRequest",
    "ExtractedConstraint",
    "ExtractedScenario",
]
