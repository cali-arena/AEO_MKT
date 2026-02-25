# Testar CORS no VM (terminal)

Rode estes comandos **no VM** (SSH: `ssh -i ... root@89.167.81.215`) para ver onde está o erro.

## 1. API está de pé?

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
```

Esperado: `200`. Se não for 200, a API não está respondendo.

```bash
curl -s http://localhost:8000/health
```

Esperado: `{"ok":true,...}`

---

## 2. Preflight OPTIONS (o que o navegador envia)

O navegador envia OPTIONS antes do GET. A API precisa responder 200 e mandar os headers CORS.

```bash
curl -s -i -X OPTIONS http://localhost:8000/metrics/latest \
  -H "Origin: https://aeo-mkt.vercel.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type"
```

**O que conferir na saída:**
- **Status:** tem que ser `200` ou `204`. Se for `401`, o auth está bloqueando OPTIONS (precisa do fix do auth que libera OPTIONS).
- **Headers:** deve aparecer algo como:
  - `Access-Control-Allow-Origin: https://aeo-mkt.vercel.app`
  - `Access-Control-Allow-Methods: ...`
  - `Access-Control-Allow-Headers: ...`

Se vier **401** e não tiver `Access-Control-Allow-Origin`, o problema é o auth bloqueando OPTIONS. Solução: fazer deploy do fix (auth deixa OPTIONS passar) e rebuild da API no VM.

---

## 3. GET com Origin (requisição real)

```bash
curl -s -i http://localhost:8000/metrics/latest \
  -H "Origin: https://aeo-mkt.vercel.app" \
  -H "Authorization: Bearer tenant:coast2coast"
```

**Conferir:** status 200 e na resposta o header `Access-Control-Allow-Origin: https://aeo-mkt.vercel.app`.

---

## 4. CORS que a API está usando (dentro do container)

```bash
cd /root/AEO_MKT
docker compose -f infra/docker-compose.yml --env-file .env exec api env | grep CORS
```

Esperado: `CORS_ALLOW_ORIGINS=https://aeo-mkt.vercel.app,...`

Se estiver vazio ou diferente, o container não está vendo o `.env` certo. Reinicie com:

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d --force-recreate api
```

---

## 5. Túnel Cloudflare está no ar? (dashboard usa a URL do túnel)

O navegador chama **https://emission-derived-out-aus.trycloudflare.com**, não localhost. Se o túnel caiu, dá "Failed to fetch".

**No VM:** ver se o processo está rodando:
```bash
pgrep -a cloudflared
```
Se não aparecer nada, o túnel parou. Subir de novo:
```bash
nohup cloudflared tunnel --url http://localhost:8000 > /root/cloudflared.log 2>&1 &
```
(A URL pode mudar; se mudar, atualize `NEXT_PUBLIC_API_BASE` no Vercel.)

**Testar CORS pela URL do túnel** (no VM ou no PC):
```bash
curl -s -i -X OPTIONS "https://emission-derived-out-aus.trycloudflare.com/metrics/latest" \
  -H "Origin: https://aeo-mkt.vercel.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type"
```
Conferir: status 200 e na resposta o header `access-control-allow-origin: https://aeo-mkt.vercel.app`. Se não tiver, o túnel/Cloudflare pode estar alterando a resposta.

---

## 6. Resumo do que fazer

| Teste | Resultado | Ação |
|-------|-----------|------|
| 1. Health 200 | OK | API no ar. |
| 2. OPTIONS 200 + header Allow-Origin | OK | CORS preflight ok. |
| 2. OPTIONS 401 | Erro | Auth bloqueando OPTIONS → fazer deploy do fix no auth e rebuild da API no VM. |
| 4. CORS vazio no container | Erro | Reiniciar API com `--env-file .env` e `--force-recreate`. |

Depois de corrigir no VM, testar de novo pelo navegador em https://aeo-mkt.vercel.app (refresh forte: Ctrl+F5).
