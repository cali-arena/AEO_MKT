"""SQLAlchemy models. All tables include tenant_id; queries MUST filter by tenant_id."""

from apps.api.models.ac_embedding import ACEmbedding
from apps.api.models.answer_cache import AnswerCache
from apps.api.models.base import Base
from apps.api.models.ec_embedding import ECEmbedding
from apps.api.models.ec_version import ECVersion
from apps.api.models.entity import Entity
from apps.api.models.entity_mention import EntityMention
from apps.api.models.eval_domain import EvalDomain
from apps.api.models.eval_result import EvalResult
from apps.api.models.eval_run import EvalRun
from apps.api.models.evidence import Evidence
from apps.api.models.ingestion_stats_daily import IngestionStatsDaily
from apps.api.models.monitor_event import MonitorEvent
from apps.api.models.raw_page import RawPage
from apps.api.models.relation import Relation
from apps.api.models.section import Section
from apps.api.models.tenant_index_version import TenantIndexVersion

__all__ = [
    "ACEmbedding",
    "AnswerCache",
    "Base",
    "ECEmbedding",
    "ECVersion",
    "Entity",
    "EntityMention",
    "EvalDomain",
    "EvalResult",
    "EvalRun",
    "Evidence",
    "IngestionStatsDaily",
    "MonitorEvent",
    "RawPage",
    "Relation",
    "Section",
    "TenantIndexVersion",
]
