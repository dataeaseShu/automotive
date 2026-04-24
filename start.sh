#!/usr/bin/env bash
# Lumax 本地启动脚本
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "=== Lumax AI Copilot 启动 ==="

# ─── 后端 ───────────────────────────────────────────────
echo "→ 安装后端依赖..."
cd "$BACKEND"

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  已创建 .env，请填写 DASHSCOPE_API_KEY 后重启"
fi

echo "→ 启动后端 (http://localhost:8000) ..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# ─── 前端 ───────────────────────────────────────────────
echo "→ 安装前端依赖..."
cd "$FRONTEND"
npm install --silent

echo "→ 启动前端 (http://localhost:3000) ..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 服务已启动："
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '已停止'" INT TERM
wait
