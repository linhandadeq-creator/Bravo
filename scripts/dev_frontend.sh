#!/usr/bin/env bash
# Start the Next.js frontend for local development.
set -euo pipefail

cd "$(dirname "$0")/../frontend"

if [ ! -d "node_modules" ]; then
  npm install
fi

export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:8000}"
exec npm run dev
