"""
计划生成与提交服务
- 从会话草稿生成预览结构
- 用户确认后提交到巨量接口
"""
from typing import Any
from datetime import date

from app.models.session import Session
from app.models.slots import BidStrategyType, LocationType, ScheduleValue
from app.adapters.mock_adapter import MockAdapter
from app.adapters.juliang_adapter import JuliangAdapter
from app.config import get_settings

_settings = get_settings()
_adapter = MockAdapter() if _settings.USE_MOCK else JuliangAdapter()


def build_preview(session: Session) -> dict[str, Any]:
    """
    从会话状态构建计划预览结构。
    包含：槽位解析说明 + 选中商品 + 绑定信息 + 成片列表 + 出价/预算/排期
    """
    slots = session.slots

    # 地域描述
    location_desc = "未设置"
    if slots.location:
        loc = slots.location.value
        if isinstance(loc, dict):
            ltype = loc.get("type")
            if ltype == LocationType.RADIUS:
                location_desc = f"周边 {loc.get('km', '?')} 公里"
            elif ltype == LocationType.CITY:
                location_desc = "同城投放"
            elif ltype == LocationType.NATIONWIDE:
                location_desc = "全国投放"

    # 出价策略描述
    bid_desc = "智能出价"
    if slots.bid_strategy:
        bid = slots.bid_strategy.value
        if isinstance(bid, dict):
            if bid.get("type") == BidStrategyType.MANUAL:
                amount = bid.get("amount")
                bid_desc = f"手动出价 {amount} 元" if amount else "手动出价（金额待确认）"

    # 排期描述
    schedule_desc = "默认7天"
    if slots.schedule:
        sched = slots.schedule.value
        if isinstance(sched, dict):
            days = sched.get("days", 7)
            start = sched.get("start_date") or date.today().isoformat()
            time_slots = sched.get("time_slots") or []
            slot_names = {"morning": "早间", "evening": "晚间", "all_day": "全天"}
            ts_desc = "、".join(slot_names.get(ts, ts) for ts in time_slots) or "全天"
            schedule_desc = f"{start} 起，{days} 天，{ts_desc}"

    # 槽位解析说明（可解释性）
    slot_explanations = {}
    for field_name in ["vehicle", "scene", "goal", "location", "audience", "budget", "bid_strategy", "schedule"]:
        slot = getattr(slots, field_name)
        if slot and slot.source:
            slot_explanations[field_name] = f"「{slot.source}」→ 已解析"

    preview = {
        "product": session.selected_product,
        "audience_package": {
            "id": session.bound_audience_id,
            "name": session.selected_product.get("audience_package_name") if session.selected_product else None,
        } if session.selected_product else None,
        "targeting_package": {
            "id": session.bound_targeting_id,
            "name": session.selected_product.get("targeting_package_name") if session.selected_product else None,
        } if session.selected_product else None,
        "vehicle": slots.vehicle.value if slots.vehicle else None,
        "scene": slots.scene.value if slots.scene else None,
        "goal": slots.goal.value if slots.goal else None,
        "location": location_desc,
        "audience": slots.audience.value if slots.audience else None,
        "budget": f"{slots.budget.value:,} 元" if slots.budget else "未设置",
        "bid_strategy": bid_desc,
        "schedule": schedule_desc,
        "creatives": session.selected_creative_ids,
        "creative_count": len(session.selected_creative_ids),
        "slot_explanations": slot_explanations,
    }

    session.plan_draft = preview
    return preview


async def submit_plan(session: Session) -> dict[str, Any]:
    """提交计划到巨量接口"""
    if not session.plan_draft:
        build_preview(session)

    plan_data = {
        "product_id": session.selected_product_id,
        "audience_package_id": session.bound_audience_id,
        "targeting_package_id": session.bound_targeting_id,
        "creative_ids": session.selected_creative_ids,
        "budget": session.slots.budget.value if session.slots.budget else 0,
        "bid_strategy": session.slots.bid_strategy.value if session.slots.bid_strategy else {"type": "auto"},
        "schedule": session.slots.schedule.value if session.slots.schedule else {"days": 7},
        "location": session.slots.location.value if session.slots.location else None,
        "scene": session.slots.scene.value if session.slots.scene else None,
        "goal": session.slots.goal.value if session.slots.goal else None,
    }

    result = await _adapter.create_plan(plan_data)
    if result.get("success"):
        session.plan_id = result.get("plan_id")
    return result
