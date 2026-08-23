#!/bin/bash
set -u
ROOT=/tmp/anchor_e2e
rm -rf "$ROOT"; mkdir -p "$ROOT"/{central,devA,devB}
PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null; done; }
trap cleanup EXIT

start() { # name role port db [extra env...]
  local name=$1 role=$2 port=$3; shift 3
  local dir="$ROOT/$name"
  env ANCHOR_DATABASE_URL="sqlite:///$dir/anchor.db" \
      ANCHOR_DATA_DIR="$dir/data" ANCHOR_ATTACHMENTS_DIR="$dir/data/attachments" \
      ANCHOR_ROLE="$role" ANCHOR_PORT=$port "$@" \
      uv run uvicorn anchor_server.main:app --port $port >"$dir/server.log" 2>&1 &
  PIDS+=($!)
}

wait_up() { # port [token]
  for i in $(seq 1 30); do
    curl -sf "http://127.0.0.1:$1/api/v1/healthz" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  echo "FAIL: port $1 never came up"; return 1
}

TOKEN=e2e-secret
# migrate each db first
for n in central devA devB; do
  ANCHOR_DATABASE_URL="sqlite:///$ROOT/$n/anchor.db" uv run alembic upgrade head >/dev/null 2>&1
done

start central central 23201 ANCHOR_AUTH_ENABLED=true ANCHOR_API_TOKEN=$TOKEN
wait_up 23201 || exit 1
start devA device 23202 ANCHOR_CENTRAL_URL=http://127.0.0.1:23201 ANCHOR_SYNC_TOKEN=$TOKEN ANCHOR_SYNC_INTERVAL=4
start devB device 23203 ANCHOR_CENTRAL_URL=http://127.0.0.1:23201 ANCHOR_SYNC_TOKEN=$TOKEN ANCHOR_SYNC_INTERVAL=4
wait_up 23202 && wait_up 23203 || exit 1

echo "== 1. device A 创建条目（含附件）"
curl -sf -X POST http://127.0.0.1:23202/api/v1/items/ -H 'Content-Type: application/json' \
  -d '{"title":"E2E Paper","item_type":"journalArticle","year":2026,"authors":[{"lastName":"Wang"}]}' > "$ROOT/item.json"
IID=$(python3 -c "import json;print(json.load(open('$ROOT/item.json'))['id'])")
curl -sf -X POST "http://127.0.0.1:23202/api/v1/items/$IID/attachments" \
  -F "file=@/tmp/anchor_e2e_item.pdf;type=application/pdf" >/dev/null 2>&1 || \
  { echo "E2E pdf" > /tmp/anchor_e2e_item.pdf && curl -sf -X POST "http://127.0.0.1:23202/api/v1/items/$IID/attachments" -F "file=@/tmp/anchor_e2e_item.pdf;type=application/pdf" >/dev/null; }

echo "== 2. 等待 A 推送（loop tick 5s），查中心端"
sleep 8
CENTRAL=$(curl -sf http://127.0.0.1:23201/api/v1/items/ -H "Authorization: Bearer $TOKEN")
echo "$CENTRAL" | grep -q "E2E Paper" && echo "OK: 中心端已收到" || { echo "FAIL: 中心端没有"; echo "$CENTRAL"; exit 1; }
echo "$CENTRAL" | grep -q '"available":false' && echo "OK: 中心端附件标记为 available=false（文件不在中心，符合设计）" || echo "NOTE: 中心端附件 available 标志非 false"

echo "== 3. 等待 B 轮询拉取（interval 4s）"
sleep 8
curl -sf http://127.0.0.1:23203/api/v1/items/ | grep -q "E2E Paper" && echo "OK: 设备 B 已同步到该条目" || { echo "FAIL: B 没有"; exit 1; }
BATT=$(curl -sf "http://127.0.0.1:23203/api/v1/items/$IID" | python3 -c "import json,sys;a=json.load(sys.stdin)['attachments'];print(a[0]['available'] if a else 'none')")
[ "$BATT" = "False" ] && echo "OK: B 上附件显示待同步（字节走 Syncthing，不在 HTTP 同步范围）" || echo "NOTE: B 附件 available=$BATT"

echo "== 4. 离线写入恢复：停中心端，A 再写一条，重启中心端"
kill "${PIDS[0]}" 2>/dev/null; sleep 1
curl -sf -X POST http://127.0.0.1:23202/api/v1/items/ -H 'Content-Type: application/json' -d '{"title":"Offline Write"}' >/dev/null
sleep 7
curl -sf http://127.0.0.1:23201/api/v1/healthz 2>/dev/null && echo "unexpected: central still up" || echo "OK: 中心端已停，A 的写入积压在 outbox"
start central central 23201 ANCHOR_AUTH_ENABLED=true ANCHOR_API_TOKEN=$TOKEN
wait_up 23201 || exit 1
sleep 10
curl -sf http://127.0.0.1:23201/api/v1/items/ -H "Authorization: Bearer $TOKEN" | grep -q "Offline Write" && echo "OK: 中心端恢复后收到离线期间的写入" || { echo "FAIL: 离线写入没推上去"; exit 1; }
sleep 12
curl -sf http://127.0.0.1:23203/api/v1/items/ | grep -q "Offline Write" && echo "OK: B 也收到了离线写入" || echo "FAIL: B 未收到离线写入"

echo "== 5. 同步状态端点"
curl -sf http://127.0.0.1:23202/api/v1/sync/status
echo
echo "ALL E2E CHECKS DONE"
