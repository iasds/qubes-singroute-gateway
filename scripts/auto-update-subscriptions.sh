#!/bin/bash
# Auto-update sing-box subscriptions
# Called by systemd timer (update-subscriptions.timer)
# Reads from singctl subscriptions, fetches latest nodes, syncs to config, restarts sing-box

LOG_TAG="singbox-auto-update"
LOCK_FILE="/tmp/singbox-update.lock"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE" 2>/dev/null)
    if kill -0 "$pid" 2>/dev/null; then
        logger -t "$LOG_TAG" "另一个更新进程正在运行 (PID $pid)，跳过"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

logger -t "$LOG_TAG" "开始自动更新订阅..."

cd /usr/local/lib
RESULT=$(python3 -c "
from singctl.subs import update_all_subscriptions, sync_nodes_to_config
results = update_all_subscriptions()
for name, count, err in results:
    if err:
        print(f'FAIL {name}: {err}')
    else:
        print(f'OK {name}: {count}')
count = sync_nodes_to_config()
print(f'SYNC {count}')
" 2>&1)

EXIT_CODE=$?

# Log results
while IFS= read -r line; do
    logger -t "$LOG_TAG" "$line"
done <<< "$RESULT"

# Restart sing-box if sync succeeded
if echo "$RESULT" | grep -q "^SYNC"; then
    NODE_COUNT=$(echo "$RESULT" | grep "^SYNC" | awk '{print $2}')
    if [ "$NODE_COUNT" -gt 0 ] 2>/dev/null; then
        systemctl restart sing-box
        logger -t "$LOG_TAG" "sing-box 已重启 ($NODE_COUNT 个节点)"
    else
        logger -t "$LOG_TAG" "警告: 0 个节点，不重启 sing-box"
    fi
fi

logger -t "$LOG_TAG" "更新完成"
