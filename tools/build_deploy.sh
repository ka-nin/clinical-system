#!/usr/bin/env bash
# Builds a clean folder containing only what the website needs, ready for `wasmer deploy`.
# Leaves out: your local database, tests, design files (incl. the licensed Adobe Stock original),
# demo-accounts.txt, .env, the virtualenv and this tools folder.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/build/deploy"
SECRETS="$ROOT/build/deploy-secrets.env"
PY="$ROOT/.venv/bin/python"

rm -rf "$OUT"
mkdir -p "$OUT"
cd "$ROOT"
cp -R apps config templates static manage.py pyproject.toml .python-version app.yaml "$OUT/"
cp requirements.txt "$OUT/requirements.txt"
find "$OUT" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$OUT" -name "*.pyc" -delete

# Pre-collect static files (with hashed names, as production expects) so the server needs no build step.
(cd "$OUT" && DJANGO_SETTINGS_MODULE=config.settings.prod DEMO_MODE=1 \
  DJANGO_SECRET_KEY="build-only-not-a-real-key-0123456789abcdefghijklmnop" \
  DB_HOST=build DB_NAME=build DB_USERNAME=build DB_PASSWORD=build \
  "$PY" manage.py collectstatic --noinput --verbosity 0)

# Secrets live OUTSIDE the deploy folder, so they are never uploaded.
if [ ! -f "$SECRETS" ]; then
  KEY="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(60))')"
  PASS="$("$PY" -c 'import secrets; w=["Maple","River","Cedar","Harbor","Summit","Willow"]; print(secrets.choice(w)+"-"+secrets.choice(w)+"-"+str(secrets.randbelow(9000)+1000))')"
  printf 'DJANGO_SECRET_KEY=%s\nDEMO_PASSWORD=%s\n' "$KEY" "$PASS" > "$SECRETS"
  chmod 600 "$SECRETS"
  echo "Created $SECRETS (keep it private; it holds the demo password)."
fi

echo "Deploy folder ready: $OUT"
echo "Files: $(find "$OUT" -type f | wc -l | tr -d ' '), size: $(du -sh "$OUT" | cut -f1)"
