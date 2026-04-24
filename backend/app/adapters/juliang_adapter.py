"""
巨量本地推真实 API 适配器（部分接口可用时使用）
不可用接口自动降级到 MockAdapter。
"""
import hashlib
import hmac
import time
import json
from typing import Any

import httpx

from app.config import get_settings
from app.adapters.mock_adapter import MockAdapter

_mock = MockAdapter()


def _sign(app_id: str, app_secret: str, method: str, params: dict) -> dict:
    """巨量接口签名（示意，具体算法按官方文档实现）"""
    timestamp = str(int(time.time()))
    param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sign_str = f"{app_id}&{method}&{timestamp}&{param_str}&{app_secret}"
    sign = hmac.new(app_secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    return {**params, "app_id": app_id, "timestamp": timestamp, "sign": sign}


class JuliangAdapter:
    def __init__(self):
        s = get_settings()
        self._app_id = s.JULIANG_APP_ID
        self._app_secret = s.JULIANG_APP_SECRET
        self._base = s.JULIANG_API_BASE
        self._client = httpx.AsyncClient(timeout=10.0)

    async def search_products(self, keyword: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        if not self._app_id:
            return await _mock.search_products(keyword, page, page_size)
        try:
            params = {"keyword": keyword, "page": page, "page_size": page_size}
            signed = _sign(self._app_id, self._app_secret, "product.list", params)
            resp = await self._client.get(f"{self._base}/product/list", params=signed)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return await _mock.search_products(keyword, page, page_size)

    async def get_product_bindings(self, product_id: str) -> dict[str, Any]:
        return await _mock.get_product_bindings(product_id)

    async def get_creatives(self, product_id: str, limit: int = 10) -> dict[str, Any]:
        if not self._app_id:
            return await _mock.get_creatives(product_id, limit)
        try:
            params = {"product_id": product_id, "limit": limit, "sort_by": "play_count"}
            signed = _sign(self._app_id, self._app_secret, "creative.list", params)
            resp = await self._client.get(f"{self._base}/creative/list", params=signed)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return await _mock.get_creatives(product_id, limit)

    async def upload_material(self, filename: str, content: bytes) -> dict[str, Any]:
        return await _mock.upload_material(filename, content)

    async def create_plan(self, plan_data: dict[str, Any]) -> dict[str, Any]:
        if not self._app_id:
            return await _mock.create_plan(plan_data)
        try:
            signed = _sign(self._app_id, self._app_secret, "plan.create", {})
            resp = await self._client.post(
                f"{self._base}/plan/create",
                params=signed,
                json=plan_data,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return await _mock.create_plan(plan_data)
