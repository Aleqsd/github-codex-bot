# 🤖 GitHub Codex Bot

This bot listens to GitHub webhooks for issues and comments created by your Product Owner (`GROBimbo`) and automatically generates **Codex-ready prompts** you can paste into your Codex CLI to implement new features for your repository.

---

## ⚙️ Quick setup

### 1. Installation

```bash
cd /root
git clone https://github.com/Aleqsd/EDH-PodLog github-codex-bot
cd github-codex-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment file

Create a `.env` file:

```bash
PORT=8082
WATCH_USER=GROBimbo
REPO=Aleqsd/EDH-PodLog
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 3. Systemd service

```bash
sudo tee /etc/systemd/system/github-codex-bot.service > /dev/null <<'EOF'
[Unit]
Description=GitHub Codex Bot (FastAPI webhook)
After=network.target

[Service]
WorkingDirectory=/root/github-codex-bot
ExecStart=/root/github-codex-bot/venv/bin/python bot.py
EnvironmentFile=/root/github-codex-bot/.env
Restart=always
User=root
StandardOutput=append:/var/log/github-codex-bot.log
StandardError=append:/var/log/github-codex-bot.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable github-codex-bot
sudo systemctl start github-codex-bot
```

### 4. Logs

```bash
sudo tail -f /var/log/github-codex-bot.log
```

---

## 🔧 Update command

Use the included `Makefile`:

```bash
make update
```

This pulls the latest code, reinstalls dependencies, and restarts the bot.

---

## 🧠 Test webhook manually

```bash
curl -X POST https://vps.zqsdev.com/github-webhook-codex   -H "Content-Type: application/json"   -d '{"action": "opened", "sender": {"login": "GROBimbo"}, "issue": {"number": 1, "title": "Test feature", "body": "Add deck export to Moxfield"}}'
```

---

MIT © Aleqsd
