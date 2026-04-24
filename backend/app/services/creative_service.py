"""
成片推荐服务
- 按"最高播放量"排序取前 MAX_CREATIVES 条
- 返回推荐列表（含标签字段 labels）
- 上传后素材直接加入候选池
"""
from typing import Any

from app.config import get_settings
from app.adapters.mock_adapter import MockAdapter
from app.adapters.juliang_adapter import JuliangAdapter

_settings = get_settings()
_adapter = MockAdapter() if _settings.USE_MOCK else JuliangAdapter()


async def recommend_creatives(product_id: str) -> list[dict[str, Any]]:
    """
    返回按播放量排序的前 MAX_CREATIVES 条成片，供用户删减。
    """
    MAX = _settings.MAX_CREATIVES
    result = await _adapter.get_creatives(product_id, limit=MAX)
    creatives = result.get("creatives", [])
    # 确保按播放量降序（接口可能未排序）
    creatives.sort(key=lambda c: c.get("play_count", 0), reverse=True)
    return creatives[:MAX]


async def upload_material(filename: str, content: bytes) -> dict[str, Any]:
    """上传视频素材，返回素材信息（可直接加入候选成片池）"""
    return await _adapter.upload_material(filename, content)
