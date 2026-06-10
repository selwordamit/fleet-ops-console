# Simulator image: a standalone Python service that talks ONLY to the backend REST API.
# It never connects to Postgres or Redis directly.
FROM python:3.12-slim

# Unbuffered stdout/stderr so telemetry tick logs appear immediately.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Working dir is the import root. Running `python -m simulator.app.main` from here
# puts this directory on sys.path, so the `simulator` package is importable and
# placement.py resolves scenario files at simulator/scenarios/... (parents[2] == /sim).
WORKDIR /sim

# Install dependencies first so this layer stays cached when only sim code changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the simulator package into /sim/simulator (app/ + scenarios/ + __init__.py).
COPY . ./simulator

# Configuration is read from environment variables (BACKEND_URL, SIMULATION_MODE,
# AGENT_COUNT, TELEMETRY_INTERVAL_SECONDS, ...) — see config.py / docs/simulator-usage.md.
CMD ["python", "-m", "simulator.app.main"]
