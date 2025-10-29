# --- GitHub Codex Bot Makefile ---

VENV = venv
PYTHON = $(VENV)/bin/python
SERVICE = github-codex-bot
WORKDIR = /root/github-codex-bot

# --- Setup and install dependencies ---
setup:
	@echo "📦 Creating virtual environment and installing dependencies..."
	python3 -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -r requirements.txt
	@echo "✅ Setup complete."

# --- Start the bot manually ---
run:
	@echo "🚀 Starting bot manually..."
	. $(VENV)/bin/activate && $(PYTHON) bot.py

# --- Systemd controls ---
start:
	sudo systemctl start $(SERVICE)
	@echo "✅ Service started."

stop:
	sudo systemctl stop $(SERVICE)
	@echo "🛑 Service stopped."

restart:
	sudo systemctl restart $(SERVICE)
	@echo "🔁 Service restarted."

status:
	sudo systemctl status $(SERVICE) --no-pager

enable:
	sudo systemctl enable $(SERVICE)
	@echo "🔒 Service enabled at boot."

disable:
	sudo systemctl disable $(SERVICE)
	@echo "🧹 Service disabled from boot."

# --- Update repo and restart bot ---
update:
	@echo "⬇️  Pulling latest code..."
	cd $(WORKDIR) && git pull
	@echo "📦 Updating dependencies..."
	. $(VENV)/bin/activate && pip install -r requirements.txt
	@echo "🔁 Restarting service..."
	sudo systemctl restart $(SERVICE)
	@echo "✅ Bot updated and restarted."

# --- View logs ---
logs:
	sudo tail -n 30 -f /var/log/github-codex-bot.log

local-logs:
	tail -n 30 -f $(WORKDIR)/github-codex-bot.log

# --- Clean environment ---
clean:
	rm -rf $(VENV)
	@echo "🧹 Virtual environment removed."

.PHONY: setup run start stop restart status enable disable update logs local-logs clean
