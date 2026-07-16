# wxcc MCP server (HTTP transport, for Cloud Run).
#
# This image deliberately contains NO Webex credentials. Each caller presents
# their own OAuth token on the request; the server never stores one. If you find
# yourself adding a token or a .env here, stop: that reintroduces the standing
# org-admin credential this design exists to avoid.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY wxcc.py mcp_server.py mcp_http.py ./

# Don't run as root.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

# Cloud Run injects PORT (default 8080) and terminates TLS for us.
ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn mcp_http:app --host 0.0.0.0 --port ${PORT}
