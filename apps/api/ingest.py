"""Compatibility entrypoints for ingestion functions."""

from apps.api.services.ingest import ingest_domain_sync, ingest_page

__all__ = ["ingest_domain_sync", "ingest_page"]
