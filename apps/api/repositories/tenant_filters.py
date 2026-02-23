"""Tenant-scoped SQL helpers. All tenant-scoped queries MUST use these.

Provides:
  - tenant_where(model, tenant_id): binary expression for WHERE model.tenant_id == tenant_id
  - select_*_for_tenant(tenant_id): SQLAlchemy Select with tenant filter applied
  - Joins MUST enforce tenant_id on each table involved (not just one).
"""

from sqlalchemy import BinaryExpression, Select, select

from apps.api.models.ac_embedding import ACEmbedding
from apps.api.models.answer_cache import AnswerCache
from apps.api.models.ec_embedding import ECEmbedding
from apps.api.models.entity import Entity
from apps.api.models.entity_mention import EntityMention
from apps.api.models.eval_result import EvalResult
from apps.api.models.eval_run import EvalRun
from apps.api.models.evidence import Evidence
from apps.api.models.monitor_event import MonitorEvent
from apps.api.models.raw_page import RawPage
from apps.api.models.relation import Relation
from apps.api.models.section import Section


def tenant_where(model: type, tenant_id: str) -> BinaryExpression[bool]:
    """Return WHERE clause: model.tenant_id == tenant_id. Use for filters and joins."""
    col = getattr(model, "tenant_id", None)
    if col is None:
        raise ValueError(f"Model {model.__name__} has no tenant_id column")
    return col == tenant_id


def select_raw_page_for_tenant(tenant_id: str) -> Select[tuple[RawPage]]:
    """Select from raw_page with tenant filter. Add .where() for further filters."""
    return select(RawPage).where(tenant_where(RawPage, tenant_id))


def select_section_for_tenant(tenant_id: str) -> Select[tuple[Section]]:
    """Select from sections with tenant filter. Add .where() for further filters."""
    return select(Section).where(tenant_where(Section, tenant_id))


def select_ac_embedding_for_tenant(tenant_id: str) -> Select[tuple[ACEmbedding]]:
    """Select from ac_embeddings with tenant filter. Add .where() for further filters."""
    return select(ACEmbedding).where(tenant_where(ACEmbedding, tenant_id))


def select_ec_embedding_for_tenant(tenant_id: str) -> Select[tuple[ECEmbedding]]:
    """Select from ec_embeddings with tenant filter. Add .where() for further filters."""
    return select(ECEmbedding).where(tenant_where(ECEmbedding, tenant_id))


def select_evidence_for_tenant(tenant_id: str) -> Select[tuple[Evidence]]:
    """Select from evidence with tenant filter. Add .where() for further filters."""
    return select(Evidence).where(tenant_where(Evidence, tenant_id))


def select_entity_for_tenant(tenant_id: str) -> Select[tuple[Entity]]:
    """Select from entities with tenant filter. Add .where() for further filters."""
    return select(Entity).where(tenant_where(Entity, tenant_id))


def select_relation_for_tenant(tenant_id: str) -> Select[tuple[Relation]]:
    """Select from relations with tenant filter. Add .where() for further filters."""
    return select(Relation).where(tenant_where(Relation, tenant_id))


def select_entity_mention_for_tenant(tenant_id: str) -> Select[tuple[EntityMention]]:
    """Select from entity_mentions with tenant filter. Add .where() for further filters."""
    return select(EntityMention).where(tenant_where(EntityMention, tenant_id))


def select_answer_cache_for_tenant(tenant_id: str) -> Select[tuple[AnswerCache]]:
    """Select from answer_cache with tenant filter. Add .where() for further filters."""
    return select(AnswerCache).where(tenant_where(AnswerCache, tenant_id))


def select_eval_run_for_tenant(tenant_id: str) -> Select[tuple[EvalRun]]:
    """Select from eval_run with tenant filter. Add .where() for further filters."""
    return select(EvalRun).where(tenant_where(EvalRun, tenant_id))


def select_eval_result_for_tenant(tenant_id: str) -> Select[tuple[EvalResult]]:
    """Select from eval_result with tenant filter. Add .where() for further filters."""
    return select(EvalResult).where(tenant_where(EvalResult, tenant_id))


def select_monitor_event_for_tenant(tenant_id: str) -> Select[tuple[MonitorEvent]]:
    """Select from monitor_event with tenant filter. Add .where() for further filters."""
    return select(MonitorEvent).where(tenant_where(MonitorEvent, tenant_id))
