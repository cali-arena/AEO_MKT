# Build Entity Corpus (EC)

Build the Entity Corpus from tenant sections: extract entities and mentions, upsert entities, store embeddings, and record an `ec_version_hash`.

## Usage

```bash
# From project root
python scripts/build_ec.py <tenant_id>

# Or as module
python -m scripts.build_ec <tenant_id>

# Ensure tables exist first
python scripts/build_ec.py <tenant_id> --ensure-tables
```

## Requirements

- `DATABASE_URL` environment variable (default: `postgresql://postgres:postgres@localhost:5432/ai_mkt`)
- Sections must exist for the tenant (run pipeline/sectionize first)

## Behavior

1. **Load sections** – All sections for the tenant (`get_sections_for_tenant`)
2. **Extract** – Run `ec_extract.extract_entities` per section
3. **Entities** – Upsert by `(tenant_id, entity_id)`, using `canonical_name`
4. **Mentions** – Delete existing mentions for tenant, insert fresh (idempotent v1)
5. **Embeddings** – Embed canonical string per entity, delete old ec_embeddings, insert new
6. **Version** – Compute and store `ec_version_hash` in `ec_versions`

## Embedding Provider

- **ENV=test** – Uses `DeterministicEmbeddingProvider` (no network)
- **Otherwise** – Uses HuggingFace SentenceTransformer

For tests, inject a mock `embed_fn` to avoid network:

```python
def mock_embed(texts: list[str]) -> list[list[float]]:
    return [[0.0] * 384 for _ in texts]

build_ec(tenant_id, embed_fn=mock_embed)
```

## Output

Returns a dict with:

- `entities_count` – Number of unique entities
- `mentions_count` – Number of mention spans
- `indexed_ec_count` – Number of ec_embeddings stored
- `ec_version_hash` – Content-based hash (sections + entities)
