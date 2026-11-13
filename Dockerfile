# One container: FastAPI serves the API and the exported Next.js pages.

FROM node:22-slim AS web
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY next.config.mjs tsconfig.json ./
COPY app ./app
RUN npm run build                      # -> /app/out

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY core ./core
COPY evals ./evals
COPY api ./api
COPY --from=web /app/out ./out
# Build the seeded CRM into the image so a cold start doesn't have to.
RUN python -m core.crm && useradd --create-home app && chown -R app /srv
USER app
# Render (and most hosts) pass the port in $PORT.
CMD ["sh", "-c", "uvicorn api.index:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
