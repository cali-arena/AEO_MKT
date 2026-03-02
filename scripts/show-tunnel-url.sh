#!/usr/bin/env bash
# Run this ON THE VM (where cloudflared-tunnel service runs) to see the current
# tunnel URL. Then set NEXT_PUBLIC_API_BASE in Vercel to that URL and Redeploy.
# Usage: sudo ./scripts/show-tunnel-url.sh
#    or: bash scripts/show-tunnel-url.sh  (if run as root)

set -e
URL=$(journalctl -u cloudflared-tunnel -n 50 --no-pager 2>/dev/null | grep -oP 'https://[^\s]+\.trycloudflare\.com' | head -1)
if [ -z "$URL" ]; then
  echo "No tunnel URL found. Is cloudflared-tunnel running?"
  echo "  sudo systemctl status cloudflared-tunnel"
  exit 1
fi
echo "=============================================="
echo "Tunnel URL (copy to Vercel NEXT_PUBLIC_API_BASE):"
echo ""
echo "  $URL"
echo ""
echo "Vercel: Settings → Environment Variables → NEXT_PUBLIC_API_BASE"
echo "        Paste the URL above (no trailing slash), then Redeploy."
echo "=============================================="
