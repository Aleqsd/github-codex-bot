# --- GitHub Codex Bot Makefile ---

VENV = venv
SERVICE = github-codex-bot
WORKDIR = /root/github-codex-bot

# --- Setup and install dependencies ---
setup:
	@set -e; \
	if command -v py >/dev/null 2>&1; then PYTHON_CREATE="py -3"; \
	elif command -v python3 >/dev/null 2>&1; then PYTHON_CREATE="python3"; \
	elif command -v python >/dev/null 2>&1; then PYTHON_CREATE="python"; \
	else echo "❌ Could not find python interpreter on PATH"; exit 1; fi; \
	echo "📦 Creating virtual environment and installing dependencies..."; \
	rm -rf "$(VENV)"; \
	eval "$$PYTHON_CREATE -m venv \"$(VENV)\""; \
	if [ -d "$(VENV)/Scripts" ]; then VENV_PY="$(VENV)/Scripts/python.exe"; else VENV_PY="$(VENV)/bin/python"; fi; \
	if [ ! -x "$$VENV_PY" ]; then echo "❌ Unable to locate virtualenv python at $$VENV_PY"; exit 1; fi; \
	"$$VENV_PY" -m pip install -r requirements.txt; \
	echo "✅ Setup complete."

# --- Start the bot manually ---
run:
	@set -e; \
	if [ -d "$(VENV)/Scripts" ]; then VENV_PY="$(VENV)/Scripts/python.exe"; else VENV_PY="$(VENV)/bin/python"; fi; \
	if [ ! -x "$$VENV_PY" ]; then echo "❌ Virtualenv not found. Run 'make setup' first."; exit 1; fi; \
	echo "🚀 Starting bot manually..."; \
	"$$VENV_PY" bot.py

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
	@echo "📦 Refreshing virtual environment..."
	python3 -m venv "$(VENV)"
	@echo "📦 Updating dependencies..."
	"$(VENV)/bin/python" -m pip install --upgrade -r requirements.txt
	@echo "🔁 Restarting service..."
	sudo systemctl restart $(SERVICE)
	@echo "✅ Bot updated and restarted."

# --- Local testing helpers ---
test:
	@set -e; \
	if [ -d "$(VENV)/Scripts" ]; then VENV_PY="$(VENV)/Scripts/python.exe"; else VENV_PY="$(VENV)/bin/python"; fi; \
	if [ ! -x "$$VENV_PY" ]; then \
		echo "📦 Creating virtual environment..."; \
		rm -rf "$(VENV)"; \
		if command -v py >/dev/null 2>&1; then PYTHON_CREATE="py -3"; \
		elif command -v python3 >/dev/null 2>&1; then PYTHON_CREATE="python3"; \
		elif command -v python >/dev/null 2>&1; then PYTHON_CREATE="python"; \
		else echo "❌ Could not find python interpreter on PATH"; exit 1; fi; \
		eval "$$PYTHON_CREATE -m venv \"$(VENV)\""; \
		if [ -d "$(VENV)/Scripts" ]; then VENV_PY="$(VENV)/Scripts/python.exe"; else VENV_PY="$(VENV)/bin/python"; fi; \
	fi; \
	if [ ! -x "$$VENV_PY" ]; then echo "❌ Unable to locate virtualenv python at $$VENV_PY"; exit 1; fi; \
	echo "📦 Ensuring dependencies are installed..."; \
	if ! "$$VENV_PY" -m pip install --upgrade -r requirements.txt; then \
		echo "⚠️ Could not update dependencies in virtual environment. Continuing with existing environment."; \
	fi; \
	echo "🧪 Running tests..."; \
	if ! "$$VENV_PY" -m pytest; then \
		echo "⚠️ Falling back to system pytest"; \
		pytest; \
	fi

# --- View logs ---
logs:
	sudo tail -n 30 -f /var/log/github-codex-bot.log

local-logs:
	tail -n 30 -f $(WORKDIR)/github-codex-bot.log

# --- Clean environment ---
clean:
	rm -rf $(VENV)
	@echo "🧹 Virtual environment removed."

.PHONY: setup run start stop restart status enable disable update test logs local-logs clean
