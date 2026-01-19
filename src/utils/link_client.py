"""Client used to interact with the ORA backend for link codes."""

from __future__ import annotations

import logging
import secrets
import string
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class LinkClient:
    """Generate link codes locally or via the ORA backend."""

    def __init__(self, base_url: Optional[str]) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None

    async def request_link_code(self, user_id: int) -> str:
        """Return a single-use link code for the given user."""

        if not self._base_url:
            code = self._generate_dummy_code()
            logger.debug("Generated dummy link code", extra={"user_id": user_id, "code": code})
            return code

        endpoint = f"{self._base_url}/api/link/init"
        payload = {"user_id": str(user_id)}
        timeout = aiohttp.ClientTimeout(total=5)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(endpoint, json=payload) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise RuntimeError(f"ORA API returned status {response.status}: {body}")
                    data = await response.json()
            except aiohttp.ClientError as exc:  # noqa: PERF203
                raise RuntimeError("ORA APIへの接続に失敗しました。") from exc

        code = data.get("code")
        code = data.get("code")
        if not isinstance(code, str):
            logger.error(f"Invalid response from ORA API: {data}")
            raise RuntimeError(f"ORA APIの応答が不正です: {data}")

        logger.info("Link code issued", extra={"user_id": user_id})
        return code

    @staticmethod
    def _generate_dummy_code() -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(8))
