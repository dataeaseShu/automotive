"""
商品搜索服务
- 调用适配器，截断前 MAX_PRODUCTS 条
- 当 total > MAX_PRODUCTS 时，附带引导继续输入关键词的消息
"""
from typing import Any

from app.config import get_settings
from app.adapters.mock_adapter import MockAdapter
from app.adapters.juliang_adapter import JuliangAdapter

_settings = get_settings()
_adapter = MockAdapter() if _settings.USE_MOCK else JuliangAdapter()


async def search_products(keyword: str) -> dict[str, Any]:
    """
    返回结构：
    {
        "products": [...],          # 最多 MAX_PRODUCTS 条
        "total": int,               # 命中总数
        "has_more": bool,           # 是否超出展示上限
        "guidance": str | None,     # 引导文字（has_more 时附带）
    }
    """
    MAX = _settings.MAX_PRODUCTS
    result = await _adapter.search_products(keyword, page=1, page_size=MAX)
    products = result.get("products", [])[:MAX]
    total = result.get("total", len(products))
    has_more = total > MAX or result.get("has_more", False)

    guidance: str | None = None
    if has_more:
        guidance = (
            f"共找到 {total} 个相关商品，已展示前 {MAX} 个。"
            "请继续输入更多关键字来精准定位您需要的商品。"
        )
    elif len(products) == 0:
        guidance = "未找到相关商品，请尝试其他关键字（如品牌名、车型名）。"

    return {
        "products": products,
        "total": total,
        "has_more": has_more,
        "guidance": guidance,
    }


async def get_product_bindings(product_id: str) -> dict[str, Any]:
    """查询商品绑定的人群包与定向包"""
    result = await _adapter.get_product_bindings(product_id)
    return result.get("data", {})
