# Milestone 1 Acceptance

**Prerequisites:** Postgres running (`docker compose -f infra/docker-compose.yml up -d postgres`)

---

## Acceptance checklist

### Tenant isolation (no leakage)

- [ ] Cross-tenant query returns zero results from other tenants (AC, EC, evidence)
- **Proof:** `pytest apps/api/tests/test_leakage.py -v`

### Versioning

- [ ] Section `version_hash` changes when content changes; `section_id` remains stable; `raw_page.version` increments
- **Proof:** `pytest apps/api/tests/test_versioning.py -v`

### Evidence spans

- [ ] Evidence spans are retrievable and match `section.text[start_char:end_char]` exactly
- **Proof:** `pytest apps/api/tests/test_evidence_spans.py -v`

### AC vs EC separation

- [ ] AC retrieval returns section-based candidates with snippet from section text
- [ ] EC retrieval returns entity-based candidates with snippet from evidence
- [ ] AC and EC respect tenant isolation
- **Proof:** `pytest apps/api/tests/test_ac_ec_separation.py -v`

### Quote-flow exclusion

- [ ] Crawl rules mark quote-flow URLs as excluded with correct reason
- [ ] Pipeline does not write `raw_page` or `sections` for excluded URLs
- [ ] Crawl report includes excluded records with `decision=excluded`, `page_type=quote_flow`
- **Proof:** `pytest apps/api/tests/test_quote_flow_exclusion.py -v`

### End-to-end demo

- [ ] Ingest allowed URLs (2 domains), skip excluded quote-flow URLs
- [ ] Stats: raw_page by domain+page_type, sections count, excluded samples
- [ ] /retrieve/ac, index_ec, /retrieve/ec, /answer
- **Proof:** `python eval/demo_milestone1.py`

### Crawl report

- [ ] Report contains records for allowed and excluded URLs
- [ ] Counts by decision, domain, page_type; top excluded samples with reasons
- **Proof:** `python eval/print_crawl_report.py`

---

## Commands

```bash
# Run all tests (requires Postgres)
pytest -q

# Milestone 1 demo
python eval/demo_milestone1.py

# Print crawl report summary
python eval/print_crawl_report.py
```

---

## Individual test modules

| Module | What it proves |
|--------|----------------|
| `test_leakage.py` | Tenant A never sees tenant B data in retrieval/evidence |
| `test_versioning.py` | section_id stable, version_hash/content/version update on change |
| `test_evidence_spans.py` | evidence.quote_span == section.text[start_char:end_char] |
| `test_ac_ec_separation.py` | AC = section vectors, EC = entity search, tenant isolation |
| `test_quote_flow_exclusion.py` | Quote-flow URLs excluded, no DB writes, crawl report records |
