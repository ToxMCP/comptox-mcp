from __future__ import annotations

import os
from typing import Tuple


def get_api_key() -> str:
    from epacomp_tox.settings import settings

    api_key = settings.ctx_api_key or settings.ctx_api_key_legacy or settings.ctx_api_key_client
    if not api_key:
        raise ValueError(
            "CTX API key is required. Set CTX_API_KEY (preferred) or EPA_COMPTOX_API_KEY."
        )
    return api_key


def get_base_url() -> str:
    from epacomp_tox.settings import settings, LEGACY_CTX_BASE_URL

    base_url = settings.ctx_api_base_url or LEGACY_CTX_BASE_URL
    if settings.ctx_use_legacy:
        return LEGACY_CTX_BASE_URL
    return base_url


def configure_ctx_env(api_key: str | None = None, base_url: str | None = None) -> None:
    from epacomp_tox.settings import settings, LEGACY_CTX_BASE_URL

    resolved_api_key = api_key or get_api_key()
    resolved_base_url = base_url or (LEGACY_CTX_BASE_URL if settings.ctx_use_legacy else settings.ctx_api_base_url)

    os.environ.setdefault("ctx_api_host", resolved_base_url)
    os.environ.setdefault("ctx_api_accept", "application/json")
    os.environ.setdefault("ctx_x_api_key", resolved_api_key)


def get_retry_config() -> Tuple[int, float]:
    from epacomp_tox.settings import settings

    return settings.ctx_retry_attempts, settings.ctx_retry_base
