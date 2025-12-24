#!/usr/bin/env python3
from __future__ import annotations

import os
import uvicorn


def main() -> None:
    # Prefer APP_* envs; fallback to config; then legacy API_* envs; finally defaults
    host = os.environ.get("APP_HOST")
    port_str = os.environ.get("APP_PORT")

    if host is None or port_str is None:
        try:
            from src.config import get_config
            cfg = get_config().app
            host = host or cfg.host
            port_str = port_str or str(cfg.port)
        except Exception:
            pass

    host = host or os.environ.get("API_HOST", "0.0.0.0")
    port_str = port_str or os.environ.get("API_PORT", "8000")

    try:
        port = int(port_str)
    except ValueError:
        port = 8000

    reload = (
        os.environ.get("APP_RELOAD")
        or os.environ.get("API_RELOAD", "true")
    ).lower() in ("1", "true", "yes")

    uvicorn.run("api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
