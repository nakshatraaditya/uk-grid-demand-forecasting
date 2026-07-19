from __future__ import annotations
import logging
import time
import requests
from griddemand import config

logger = logging.getLogger(__name__)


def get_json(url: str, params: dict | None = None) -> dict:
    
    last_exc: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            wait = config.RETRY_BACKOFF * (2 ** (attempt - 1))
            logger.warning(
                "Request failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt, config.MAX_RETRIES, exc, wait,
            )
            if attempt < config.MAX_RETRIES:
                time.sleep(wait)
    raise RuntimeError(f"GET {url} failed after {config.MAX_RETRIES} attempts") from last_exc