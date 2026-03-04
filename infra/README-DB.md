# Database (Postgres + pgvector)

The `db` service uses **pgvector/pgvector** so that the `vector` extension works (embeddings). The image tag must match your Postgres major version.

## Check current Postgres major version

**PowerShell (from project root):**
```powershell
docker exec infra-db-1 psql -U postgres -d ai_mkt -t -c "SELECT (regexp_match(current_setting('server_version'), '^([0-9]+)'))[1] AS major;"
```

**Bash / Git Bash:**
```bash
sh infra/check-pg-version.sh
```

Use the number (15, 16, 17, 18) to pick the image tag: `pgvector/pgvector:pg16` for Postgres 16.

## If you see "$libdir/vector: No such file or directory"

The db container is still using the plain Postgres image (no pgvector binaries). Fix:

1. **On the server, ensure the compose file uses the pgvector image:**
   ```bash
   grep "image:.*pgvector" infra/docker-compose.yml
   ```
   You should see `image: pgvector/pgvector:pg16`. If you see `postgres:16`, edit `infra/docker-compose.yml` and set:
   ```yaml
   image: pgvector/pgvector:pg16
   ```
   under the `db:` service.

2. **Pull the image and recreate the db container:**
   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env pull db
   docker compose -f infra/docker-compose.yml --env-file .env up -d --force-recreate db
   ```

3. **Confirm the running image is pgvector:**
   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env ps
   ```
   The db row should show `pgvector/pgvector:pg16`, not `postgres:16`.

Do **not** remove volumes if you want to keep data. If the volume was created with a different Postgres major version, you may need to bring the stack down, remove the volume, and bring it up again (data loss):

```bash
docker compose -f infra/docker-compose.yml --env-file .env down -v
docker compose -f infra/docker-compose.yml --env-file .env up -d
```

Then re-run migrations and re-ingest as needed.
