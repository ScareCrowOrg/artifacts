#!/usr/bin/env python3
"""
Presence client for planet-beacon.

Sends a presence heartbeat to CentralHub, announcing that this planet is
online along with its list of available viewers.

Usage::

    from presence_client import send_presence
    import config

    viewers = [{"id": "dynamic-workspace", "path": "/artifacts/canonical/viewers/dynamic-workspace"}]
    await send_presence(config, viewers)
"""

import logging
from typing import List, Dict

import httpx

logger = logging.getLogger(__name__)


async def send_presence(cfg: object, viewers: List[Dict[str, str]]) -> bool:
    """
    POST a presence heartbeat to CentralHub.

    Stores ``planet:presence:{planet_id}`` in Redis L2 (server-side, via CentralHub)
    with TTL = ``PRESENCE_TTL`` seconds.

    Args:
        cfg:     Config module (or object) with PLANET_ID, PLANET_NAME, TUNNEL_FQDN,
                 CENTRALHUB_URL, CENTRALHUB_SERVICE_TOKEN, and PRESENCE_TTL attributes.
        viewers: List of viewer dicts from ``scan_viewers()``.

    Returns:
        ``True`` on HTTP 204, ``False`` on any error.
    """
    if not cfg.PLANET_ID:
        logger.error("PLANET_ID is not configured — cannot send presence heartbeat")
        return False

    if not cfg.CENTRALHUB_SERVICE_TOKEN:
        logger.error("CENTRALHUB_SERVICE_TOKEN is not configured — cannot send presence heartbeat")
        return False

    url = f"{cfg.CENTRALHUB_URL}/api/v1/planets/presence"
    payload = {
        "planet_id": cfg.PLANET_ID,
        "name": cfg.PLANET_NAME,
        "fqdn": cfg.TUNNEL_FQDN,
        "status": "online",
        "viewers": viewers,
    }
    headers = {
        "Authorization": f"Bearer {cfg.CENTRALHUB_SERVICE_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 204:
                logger.debug(
                    "Presence heartbeat sent: planet=%s fqdn=%s viewers=%d",
                    cfg.PLANET_ID,
                    cfg.TUNNEL_FQDN,
                    len(viewers),
                )
                return True
            else:
                logger.warning(
                    "Presence heartbeat rejected by CentralHub: status=%d body=%s",
                    response.status_code,
                    response.text[:200],
                )
                return False
    except httpx.RequestError as exc:
        logger.warning("Presence heartbeat request failed: %s", exc)
        return False
