#!/bin/bash
# EPA CompTox MCP Server Startup Script
# This script starts the EPA CompTox MCP server with the HTTP/WebSocket transport

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== EPA CompTox MCP Server Startup ===${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating from .env.example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${RED}ERROR: Please edit .env and set your CTX_API_KEY${NC}"
        echo "Get your API key from: https://comptox.epa.gov/dashboard/api-access"
        exit 1
    else
        echo -e "${RED}ERROR: .env.example not found${NC}"
        exit 1
    fi
fi

# Source the .env file
set -a; . ./.env; set +a

# Validate required environment variables
if [ -z "$CTX_API_KEY" ] || [ "$CTX_API_KEY" = "your_ctx_api_key_here" ]; then
    echo -e "${RED}ERROR: CTX_API_KEY not set in .env file${NC}"
    echo "Please edit .env and set your CTX_API_KEY"
    echo "Get your API key from: https://comptox.epa.gov/dashboard/api-access"
    exit 1
fi

# Set defaults if not provided
export CTX_API_BASE_URL="${CTX_API_BASE_URL:-https://comptox.epa.gov/ctx-api}"
export ENVIRONMENT="${ENVIRONMENT:-development}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

echo -e "${GREEN}Environment Configuration:${NC}"
echo "  CTX_API_BASE_URL: $CTX_API_BASE_URL"
echo "  ENVIRONMENT: $ENVIRONMENT"
echo "  LOG_LEVEL: $LOG_LEVEL"
echo "  CTX_API_KEY: ${CTX_API_KEY:0:10}... (masked)"
echo ""

# Choose the appropriate command
PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"

echo -e "${GREEN}Starting EPA CompTox MCP server on ${HOST}:${PORT}...${NC}"
echo "  HTTP/JSON-RPC endpoint: http://127.0.0.1:${PORT}/mcp"
echo "  WebSocket endpoint: ws://127.0.0.1:${PORT}/mcp/ws"
echo "  Health check: http://127.0.0.1:${PORT}/healthz"
echo ""

# Start with uvicorn (development with auto-reload)
uvicorn epacomp_tox.transport.websocket:app \
    --host "$HOST" \
    --port "$PORT" \
    --reload \
    --log-level info

# For production, use gunicorn instead:
# APP_MODULE=epacomp_tox.transport.websocket:app gunicorn -c deploy/gunicorn_conf.py
