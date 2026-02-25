# API em HTTPS (corrigir Mixed Content)

O dashboard no Vercel usa **HTTPS**. Se a API no VM for **HTTP**, o navegador bloqueia (Mixed Content). A API precisa ser acessível por **HTTPS**.

---

## Passo a passo: Cloudflare Tunnel (o que eu faria primeiro)

Sem domínio, sem abrir porta 80/443. Você roda um túnel no VM e usa a URL HTTPS que o Cloudflare mostra.

### 1. Entrar no VM

No seu PC (PowerShell):

```powershell
ssh -i $env:USERPROFILE\.ssh\hetzner-aeo root@89.167.81.215
```

### 2. Instalar cloudflared no VM

Copie e cole no terminal do VM (uma linha por vez se preferir):

```bash
cd /root
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i cloudflared.deb
cloudflared --version
```

(Se `dpkg -i` reclamar de dependência: `apt-get update && apt-get install -f -y` e depois `dpkg -i cloudflared.deb` de novo.)

### 3. Subir o túnel (URL HTTPS temporária)

No VM:

```bash
cloudflared tunnel --url http://localhost:8000
```

**Deixe esse comando rodando.** No texto que aparecer, procure uma linha tipo:

```text
Your quick Tunnel has been created! Visit it at:
https://algum-nome-aleatorio.trycloudflare.com
```

Copie essa URL **https://...** (sem barra no final). Exemplo: `https://abc-def-123.trycloudflare.com`.

### 4. Túnel sempre ligado (sobrevive ao fechar SSH e ao reboot do VM)

Para o túnel **não desligar** quando você fecha o SSH ou reinicia o VM, use um **serviço systemd** no VM.

**No VM:**

1. Copie o arquivo de serviço para o systemd (no seu PC o arquivo está em `systemd/cloudflared-tunnel.service`; no VM você pode criar direto):

```bash
sudo nano /etc/systemd/system/cloudflared-tunnel.service
```

Cole este conteúdo (salve: `Ctrl+O`, Enter, `Ctrl+X`):

```ini
[Unit]
Description=Cloudflare Tunnel to localhost:8000 (API)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/cloudflared tunnel --url http://localhost:8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cloudflared

[Install]
WantedBy=multi-user.target
```

2. Ative e inicie o serviço:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloudflared-tunnel
sudo systemctl start cloudflared-tunnel
sudo systemctl status cloudflared-tunnel
```

3. Ver a **URL do túnel** (quick tunnel gera URL nova a cada start/reboot):

```bash
sudo journalctl -u cloudflared-tunnel -n 30 --no-pager
```

Procure a linha `Visit it at: https://....trycloudflare.com` e use essa URL no Vercel.

**Importante:** Cada vez que o VM **reiniciar**, a URL do quick tunnel **muda**. Depois do reboot:

- Rode de novo: `sudo journalctl -u cloudflared-tunnel -n 30 --no-pager` e copie a nova URL.
- Atualize **NEXT_PUBLIC_API_BASE** no Vercel com essa URL e faça **Redeploy**.

Para **URL fixa** (não precisar atualizar o Vercel após reboot): use **tunnel nomeado** na Cloudflare (conta grátis) ou **domínio + Caddy** no VM (ver Opção 2 mais abaixo).

### 5. CORS no VM (.env)

No VM, edite o `.env` e inclua a origem do dashboard (Vercel). A API não precisa “conhecer” a URL do Cloudflare; só as origens do front (Vercel):

```bash
cd /root/AEO_MKT
nano .env
```

Deixe a linha assim (pode adicionar a URL do túnel se quiser; para Mixed Content não é obrigatório, CORS é para o Vercel):

```env
CORS_ALLOW_ORIGINS=https://aeo-mkt.vercel.app,https://aeo-efh97avkg-cali-arenas-projects.vercel.app,http://localhost:3000
```

Salvar: `Ctrl+O`, Enter, `Ctrl+X`. Reiniciar a API:

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d api
```

### 6. Vercel: apontar o dashboard para a URL HTTPS do túnel

1. Abra o projeto no Vercel → **Settings** → **Environment Variables**.
2. Edite **NEXT_PUBLIC_API_BASE** e coloque **exatamente** a URL do túnel (a que você copiou no passo 3), **sem barra no final**.  
   Exemplo: `https://abc-def-123.trycloudflare.com`
3. Salve.

### 7. Redeploy do dashboard

No Vercel: **Deployments** → menu **⋮** no último deploy → **Redeploy**. Aguarde terminar.

### 8. Testar

1. Abra no navegador: `https://aeo-mkt.vercel.app`
2. Faça login e entre em Overview ou Domains. O “Failed to fetch” deve sumir (sem Mixed Content).

---

**Resumo dos comandos (VM):**

```bash
# 1) SSH (no PC)
# ssh -i $env:USERPROFILE\.ssh\hetzner-aeo root@89.167.81.215

# 2) Instalar cloudflared (no VM)
cd /root
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i cloudflared.deb

# 3) Rodar túnel (anotar a URL https que aparecer)
cloudflared tunnel --url http://localhost:8000
# Ou serviço systemd (sempre ligado, sobrevive a fechar SSH e reboot):
# sudo systemctl enable --now cloudflared-tunnel
# Ver URL: sudo journalctl -u cloudflared-tunnel -n 30 --no-pager

# 4) Reiniciar API depois de ajustar CORS no .env
cd /root/AEO_MKT
docker compose -f infra/docker-compose.yml --env-file .env up -d api
```

---

## Opção 2: Domínio + Caddy no VM (URL fixa, recomendado para produção)

Você precisa de um **domínio** (ex.: `api.seudominio.com`) apontando para o IP do VM (`89.167.81.215`).

1. No seu provedor de DNS, crie um registro **A**: `api.seudominio.com` → `89.167.81.215`.

2. No VM, instale o Caddy (ele obtém certificado HTTPS automático):
   ```bash
   sudo apt install -y debian-keyring debian-archive-keyring curl
   curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
   curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
   sudo apt update && sudo apt install caddy
   ```

3. Configure o Caddy para fazer proxy para a API:
   ```bash
   sudo nano /etc/caddy/Caddyfile
   ```
   Conteúdo (troque `api.seudominio.com` pelo seu domínio):
   ```
   api.seudominio.com {
       reverse_proxy localhost:8000
   }
   ```
   Salve e reinicie: `sudo systemctl restart caddy`.

4. Abra a porta 80 e 443 no firewall (para o Let's Encrypt e HTTPS):
   ```bash
   sudo ufw allow 80
   sudo ufw allow 443
   sudo ufw reload
   ```

5. **Vercel:** `NEXT_PUBLIC_API_BASE` = `https://api.seudominio.com`  
   **VM .env:** adicione em CORS: `https://aeo-mkt.vercel.app` (e outros que usar).  
   Reinicie a API: `docker compose -f infra/docker-compose.yml --env-file .env up -d api`.

6. **Redeploy** o dashboard no Vercel.

---

## Resumo

| Situação | Ação |
|---------|------|
| Teste rápido | Cloudflare Tunnel (`cloudflared tunnel --url http://localhost:8000`) e use a URL HTTPS no Vercel. |
| Produção | Domínio A → VM, Caddy com reverse_proxy para localhost:8000, depois `NEXT_PUBLIC_API_BASE=https://api.seudominio.com` e CORS no .env. |

O WebSocket `ws://localhost:8081` costuma ser do ambiente de desenvolvimento (Next.js) ou extensão; em produção pode aparecer mas não é o que bloqueia os dados. O que bloqueia é o **Mixed Content**; ao usar HTTPS na API, o "Failed to fetch" some.
