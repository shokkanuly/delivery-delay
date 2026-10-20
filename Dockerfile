# Single image used for the api, dashboard, and seed services (compose overrides
# the command per service).
FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal; psycopg[binary] ships its own libpq.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# api: 8000, streamlit: 8501 (local/compose defaults; Railway and other PaaS
# targets inject their own $PORT at runtime -- the startup script expands it,
# falling back to 8000 so docker-compose and bare `docker run` still work).
EXPOSE 8000 8501

CMD ["sh", "scripts/start_api.sh"]
