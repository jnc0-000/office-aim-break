#!/bin/sh
set -eu

missing=""
for name in BTC_POOL_URL BTC_WORKER BTC_PASSWORD; do
  eval "value=\${$name:-}"
  if [ -z "$value" ]; then
    missing="$missing $name"
  fi
done

if [ -n "$missing" ]; then
  echo "BTC miner is not configured."
  echo "Set required environment variables:$missing"
  echo "Example:"
  echo "  BTC_POOL_URL=stratum+tcp://pool.example.com:3333"
  echo "  BTC_WORKER=wallet_or_pool_user.worker"
  echo "  BTC_PASSWORD=x"
  exit 64
fi

echo "Starting BTC CPU miner."
echo "Pool: $BTC_POOL_URL"
echo "Worker: $BTC_WORKER"
echo "Algorithm: ${BTC_ALGO:-sha256d}"
echo "Threads: ${BTC_THREADS:-1}"

exec minerd \
  --algo="${BTC_ALGO:-sha256d}" \
  --url="$BTC_POOL_URL" \
  --userpass="$BTC_WORKER:$BTC_PASSWORD" \
  --threads="${BTC_THREADS:-1}"
