#!/bin/bash
# くうっち勉強バトル サーバー起動スクリプト

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 既存プロセスを停止
echo "既存サーバーを停止中..."
lsof -ti :3456 | xargs kill -9 2>/dev/null
lsof -ti :3457 | xargs kill -9 2>/dev/null
pkill -f "caffeinate.*kanji" 2>/dev/null
sleep 0.5

# 本番サーバー起動 (port 3456)
echo "本番サーバーを起動中 → http://localhost:3456"
nohup python3 "$SCRIPT_DIR/server.py" 3456 > /tmp/kanji-prod.log 2>&1 &
PROD_PID=$!

# 開発サーバー起動 (port 3457)
echo "開発サーバーを起動中 → http://localhost:3457/index_dev.html"
nohup python3 "$SCRIPT_DIR/server.py" 3457 > /tmp/kanji-dev.log 2>&1 &
DEV_PID=$!

# スリープ抑制（両サーバーが生きている間はスリープしない）
# -s: 電源アダプタ接続中はスリープしない
# -w: 指定PIDが終了するまで継続
nohup caffeinate -s -w $PROD_PID > /tmp/kanji-caffeinate.log 2>&1 &

sleep 1

echo ""
echo "✅ 起動完了！（スリープ抑制中 ☕）"
echo "  本番: http://localhost:3456"
echo "  開発: http://localhost:3457/index_dev.html"
echo ""
echo "停止するには: kill \$(lsof -ti :3456,:3457)"
