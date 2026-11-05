#!/usr/bin/env bash
# 题库同步服务一键安装（Ubuntu / Debian，用 sudo 跑）
#   curl -fsSLO https://raw.githubusercontent.com/huzhixin210/exam-tutor/main/deploy/install_server.sh
#   sudo bash install_server.sh
set -euo pipefail

DIR=/srv/exam-bank
RAW=https://raw.githubusercontent.com/huzhixin210/exam-tutor/main/deploy/bank_server.py
PORT="${PORT:-9120}"

command -v python3 >/dev/null || { echo "缺 python3"; exit 1; }
RUN_USER="${SUDO_USER:-ubuntu}"
mkdir -p "$DIR/data"
chown -R "$RUN_USER":"$RUN_USER" "$DIR"      # 服务以 ubuntu 身份写题库，目录必须归它

echo "== 下载服务端脚本 =="
curl -fsSL "$RAW" -o "$DIR/bank_server.py"
chmod +x "$DIR/bank_server.py"

if [ -f "$DIR/token.txt" ]; then
  TOKEN=$(cat "$DIR/token.txt")
  echo "== 复用已有令牌 =="
else
  TOKEN=$(openssl rand -hex 16)
  printf '%s' "$TOKEN" > "$DIR/token.txt"
  chmod 600 "$DIR/token.txt"
  echo "== 生成新令牌 =="
fi

echo "== 写 systemd 服务 =="
cat >/etc/systemd/system/exam-bank.service <<EOF2
[Unit]
Description=exam-bank question bank sync server
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$DIR
Environment=EXAM_BANK_TOKEN=$TOKEN
Environment=EXAM_BANK_PORT=$PORT
Environment=EXAM_BANK_DATA=$DIR/data
ExecStart=/usr/bin/python3 $DIR/bank_server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF2

systemctl daemon-reload
timeout 60 systemctl enable --now exam-bank || echo "(enable 有告警，不影响使用)"
sleep 1

if command -v ufw >/dev/null && ufw status | grep -qi active; then
  ufw allow "$PORT"/tcp || true
fi

IP=$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
echo
echo "=================================================="
echo " 安装完成"
echo " 地址 : http://$IP:$PORT"
echo " 令牌 : $TOKEN"
echo " 数据 : $DIR/data"
echo
echo " 自检 : curl -s http://$IP:$PORT/healthz"
echo " 状态 : systemctl status exam-bank --no-pager"
echo " 下一步（在你自己的电脑上）："
echo "   python tools/publish_bank.py --url http://$IP:$PORT --token $TOKEN --dir \"<你的题库目录>\""
echo
echo " ⚠ 云厂商安全组还要放行 TCP $PORT，否则外网连不上"
echo "=================================================="

echo
echo "== 服务状态 =="
timeout 10 systemctl --no-pager --lines=5 status exam-bank || true
