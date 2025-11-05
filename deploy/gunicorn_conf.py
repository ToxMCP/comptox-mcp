"""
Gunicorn configuration for the EPA CompTox MCP transport service.

Values can be overridden with environment variables:
- EPACOMP_MCP_BIND: address and port to bind (default: 0.0.0.0:8000)
- EPACOMP_MCP_WORKERS: number of worker processes (default: 2 * CPU + 1)
- EPACOMP_MCP_TIMEOUT: worker timeout in seconds (default: 120)
- EPACOMP_MCP_GRACEFUL_TIMEOUT: graceful timeout in seconds (default: 30)
- EPACOMP_MCP_KEEPALIVE: keepalive in seconds (default: 5)
- EPACOMP_MCP_LOG_LEVEL: logging level (default: info)
"""

import multiprocessing
import os


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(parsed, 1)


def _str_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


bind = _str_env("EPACOMP_MCP_BIND", "0.0.0.0:8000")
workers = _int_env("EPACOMP_MCP_WORKERS", (multiprocessing.cpu_count() * 2) + 1)
worker_class = "uvicorn.workers.UvicornWorker"
timeout = _int_env("EPACOMP_MCP_TIMEOUT", 120)
graceful_timeout = _int_env("EPACOMP_MCP_GRACEFUL_TIMEOUT", 30)
keepalive = _int_env("EPACOMP_MCP_KEEPALIVE", 5)

accesslog = "-"
errorlog = "-"
loglevel = _str_env("EPACOMP_MCP_LOG_LEVEL", "info")
worker_tmp_dir = "/dev/shm"
preload_app = True
