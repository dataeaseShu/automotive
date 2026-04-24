"""
巨量本地推 API Mock 适配器
- 与正式接口保持同契约（相同入参/出参结构）
- 支持通过 USE_MOCK=True 环境变量切换
"""
import json
import os
import random
from typing import Any
from urllib.parse import quote
from app.models.slots import BidStrategyType


_BINDINGS_PATH = os.path.join(os.path.dirname(__file__), "../../data/product_bindings.json")


def _load_product_bindings() -> dict[str, dict[str, Any]]:
    with open(os.path.abspath(_BINDINGS_PATH), "r", encoding="utf-8") as f:
        return json.load(f)


def _load_mock_products() -> list[dict[str, Any]]:
    bindings = _load_product_bindings()
    products: list[dict[str, Any]] = []
    for product_id, binding in sorted(bindings.items()):
        model = str(binding.get("model") or binding.get("product_name") or product_id)
        products.append(
            {
                "product_id": product_id,
                "product_name": binding.get("product_name", product_id),
                "brand": binding.get("brand", "通用品牌"),
                "model": model,
                "thumbnail": f"https://placehold.co/120x80?text={quote(model)}",
                "status": "active",
            }
        )
    return products

_MOCK_PRODUCTS = _load_mock_products()

_MOCK_CREATIVES = [
    {"creative_id": f"cr_{i:03d}", "title": f"精选成片{i:02d}", "duration": random.randint(15, 60),
     "thumbnail": f"https://placehold.co/180x100?text=成片{i:02d}",
     "play_count": random.randint(10000, 5000000),
     "conversion_rate": round(random.uniform(0.01, 0.08), 4),
     "labels": random.sample(["最高播放", "最易成交", "近7天稳定", "近30天稳定", "爆款潜力"], k=2),
     "status": "active"}
    for i in range(1, 21)
]

# 按播放量降序排序
_MOCK_CREATIVES.sort(key=lambda x: x["play_count"], reverse=True)


class MockAdapter:
    """所有方法均为异步，与真实适配器接口保持一致"""

    async def search_products(self, keyword: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        kw = keyword.lower()
        matched = [
            p for p in _MOCK_PRODUCTS
            if kw in p["product_name"].lower()
            or kw in p["brand"].lower()
            or kw in p["model"].lower()
        ]
        total = len(matched)
        start = (page - 1) * page_size
        items = matched[start: start + page_size]
        return {
            "products": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": total > start + page_size,
        }

    async def get_product_bindings(self, product_id: str) -> dict[str, Any]:
        bindings = _load_product_bindings()
        binding = bindings.get(product_id)
        if binding:
            return {"success": True, "data": binding}
        # 若 product_bindings 中无此商品，返回通用绑定
        return {
            "success": True,
            "data": {
                "product_id": product_id,
                "audience_package_id": f"aud_{product_id}",
                "audience_package_name": "通用汽车意向人群包",
                "targeting_package_id": f"tgt_{product_id}",
                "targeting_package_name": "通用汽车标准定向包",
            },
        }

    async def get_creatives(self, product_id: str, limit: int = 10) -> dict[str, Any]:
        return {
            "success": True,
            "creatives": _MOCK_CREATIVES[:limit],
            "total": len(_MOCK_CREATIVES),
        }

    async def upload_material(self, filename: str, content: bytes) -> dict[str, Any]:
        import uuid
        material_id = f"mat_{uuid.uuid4().hex[:8]}"
        return {
            "success": True,
            "material_id": material_id,
            "material_name": filename,
            "thumbnail": f"https://placehold.co/180x100?text={filename[:8]}",
            "play_count": 0,
            "labels": ["新上传"],
            "status": "pending_review",
        }

    async def create_plan(self, plan_data: dict[str, Any]) -> dict[str, Any]:
        import uuid
        plan_id = f"plan_{uuid.uuid4().hex[:10]}"
        return {
            "success": True,
            "plan_id": plan_id,
            "status": "pending",
            "message": "计划已提交，审核中",
        }
