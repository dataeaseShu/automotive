from __future__ import annotations

import re
from typing import Any, Optional

from app.deerflow import DeerFlowEngine
from app.models.session import MessageType, Session, SessionState
from app.models.slots import SlotField
from app.nlp.parser import parse_slots, parse_slots_with_intent
from app.services.creative_service import recommend_creatives
from app.services.plan_service import submit_plan
from app.services.product_service import get_product_bindings, search_products
from app.skills.base import Skill, SkillResult

_GENERAL_HELP_PATTERNS = [
    re.compile(r"^(你好|您好|嗨|hi|hello)[!！?？]?$", re.IGNORECASE),
    re.compile(r"你是谁|你是干什么的|你能做什么|介绍一下你自己|自我介绍"),
    re.compile(r"怎么用|如何使用|帮助|使用说明|功能介绍"),
]

_CAMPAIGN_KEYWORDS = [
    "投放", "推广", "建计划", "创建计划", "新建计划", "预算", "出价", "同城", "全国",
    "直播", "短视频", "线索", "门店", "试驾", "车型", "商品", "巨量", "引流",
]

_CONFIRM_TEXTS = {"确认推送计划至巨量引擎", "确认推送", "确认提交", "提交"}

_REQUIRED_ORDER = [
    "scene",
    "goal",
    "location",
    "audience",
    "budget",
    "bid_strategy",
    "schedule",
]

_FIELD_PROMPTS = {
    "scene": "请确认营销场景：短视频 或 直播。",
    "goal": "请确认营销目标：门店引流 / 试驾预约 / 线索收集。",
    "location": "请确认投放地域：同城 / 全国 / 周边X公里。",
    "audience": "请设置投放人群（如：男性，25-40岁）。",
    "budget": "请设置预算（如：50000元 或 10万）。",
    "bid_strategy": "请设置出价策略：智能出价 或 手动出价X元。",
    "schedule": "请设置排期（如：投放7天 / 30天）。",
}


class AutomotiveMarketingSkill(Skill):
    name = "automotive_marketing"

    def __init__(self) -> None:
        # deerFlow 风格：按阶段注册处理节点
        self.flow = DeerFlowEngine()
        self.flow.register("product", self._handle_product_stage)
        self.flow.register("creative", self._handle_creative_stage)
        self.flow.register("slot", self._handle_slot_stage)
        self.flow.register("preview", self._handle_preview_stage)
        self.flow.register("fallback", self._handle_fallback_stage)

    async def can_handle(self, session: Session, text: str) -> bool:
        if session.active_skill == self.name:
            return True
        if session.state in {
            SessionState.PRODUCT_SEARCH,
            SessionState.PRODUCT_SELECTED,
            SessionState.CREATIVE_SELECTION,
            SessionState.SLOT_FILLING,
            SessionState.PREVIEW,
        }:
            return True
        normalized = text.strip().lower()
        return any(keyword in normalized for keyword in _CAMPAIGN_KEYWORDS)

    async def handle_message(self, session: Session, text: str) -> SkillResult:
        reply_messages: list[dict[str, Any]] = []

        if self._should_return_welcome(text) and session.active_skill != self.name:
            welcome = (
                "您好！我是智能投手 Lumax。\n"
                "我会一步一步帮您完成投放计划：先选商品，再选宣传视频，再配置投放参数，最后生成计划。"
            )
            session.add_message("assistant", welcome)
            reply_messages.append({"type": MessageType.TEXT, "content": welcome})
            return SkillResult(handled=True, messages=reply_messages)

        if text in _CONFIRM_TEXTS:
            if session.state != SessionState.PREVIEW:
                msg = "还未到提交阶段，请先完成商品、宣传视频和投放参数配置。"
                session.add_message("assistant", msg)
                reply_messages.append({"type": MessageType.TEXT, "content": msg})
                return SkillResult(handled=True, messages=reply_messages)

            if not session.selected_product_id:
                msg = "请先选择要推广的商品。"
                session.add_message("assistant", msg)
                reply_messages.append({"type": MessageType.TEXT, "content": msg})
                return SkillResult(handled=True, messages=reply_messages)

            result = await submit_plan(session)
            if result.get("success"):
                session.state = SessionState.SUBMITTED
                done_msg = f"计划提交成功，计划ID：{result.get('plan_id')}"
                session.add_message("assistant", done_msg)
                reply_messages.append({"type": MessageType.TEXT, "content": done_msg})
            else:
                err_msg = "计划提交失败，请稍后重试。"
                session.add_message("assistant", err_msg)
                reply_messages.append({"type": MessageType.ERROR, "content": err_msg})
            return SkillResult(handled=True, messages=reply_messages)

        stage = self._resolve_stage(session)
        return await self.flow.route(stage, session, text)

    def _resolve_stage(self, session: Session) -> str:
        if session.selected_product_id is None:
            return "product"
        if session.state == SessionState.CREATIVE_SELECTION:
            return "creative"
        if session.state == SessionState.PREVIEW:
            return "preview"
        if session.state in {SessionState.SLOT_FILLING, SessionState.PRODUCT_SELECTED}:
            return "slot"
        return "fallback"

    async def _handle_product_stage(self, session: Session, text: str) -> SkillResult:
        is_new_intent = any(kw in text for kw in _CAMPAIGN_KEYWORDS)
        if session.state == SessionState.PRODUCT_SEARCH and not is_new_intent:
            return await self._search_products_step(session, text)

        session.slots, _ = await parse_slots_with_intent(text, session.slots)
        return await self._search_products_step(session, text)

    async def _handle_creative_stage(self, session: Session, _text: str) -> SkillResult:
        reply_messages: list[dict[str, Any]] = []
        if not session.selected_creative_ids:
            msg = "请先在上方选择至少1个宣传视频，然后输入“下一步”。"
            session.add_message("assistant", msg)
            reply_messages.append({"type": MessageType.TEXT, "content": msg})
            return SkillResult(handled=True, messages=reply_messages)

        session.state = SessionState.SLOT_FILLING
        msg = "已完成宣传视频选择。接下来我们补充投放参数。"
        session.add_message("assistant", msg)
        reply_messages.append({"type": MessageType.TEXT, "content": msg})
        next_prompt = self._next_slot_prompt(session)
        if next_prompt:
            session.add_message("assistant", next_prompt)
            reply_messages.append({"type": MessageType.TEXT, "content": next_prompt})
        else:
            reply_messages.extend(self._build_plan_confirm_messages(session))
        return SkillResult(handled=True, messages=reply_messages)

    async def _handle_slot_stage(self, session: Session, text: str) -> SkillResult:
        reply_messages: list[dict[str, Any]] = []
        session.slots = await parse_slots(text, session.slots)
        next_prompt = self._next_slot_prompt(session)
        if next_prompt:
            session.add_message("assistant", next_prompt)
            reply_messages.append({"type": MessageType.TEXT, "content": next_prompt})
        else:
            reply_messages.extend(self._build_plan_confirm_messages(session))
        return SkillResult(handled=True, messages=reply_messages)

    async def _handle_preview_stage(self, session: Session, text: str) -> SkillResult:
        session.slots = await parse_slots(text, session.slots)
        return SkillResult(handled=True, messages=self._build_plan_confirm_messages(session))

    async def _handle_fallback_stage(self, session: Session, text: str) -> SkillResult:
        reply_messages: list[dict[str, Any]] = []
        session.slots = await parse_slots(text, session.slots)
        next_prompt = self._next_slot_prompt(session)
        if next_prompt:
            session.state = SessionState.SLOT_FILLING
            session.add_message("assistant", next_prompt)
            reply_messages.append({"type": MessageType.TEXT, "content": next_prompt})
        else:
            reply_messages.extend(self._build_plan_confirm_messages(session))
        return SkillResult(handled=True, messages=reply_messages)

    async def handle_select_product(self, session: Session, product_id: str, product: dict[str, Any]) -> SkillResult:
        session.selected_product_id = product_id
        session.selected_product = product

        selected_vehicle = (
            product.get("model")
            or product.get("product_name")
            or product_id
        )
        session.slots.vehicle = SlotField(
            value=str(selected_vehicle),
            confidence=1.0,
            source="selected_product",
        )

        bindings = await get_product_bindings(product_id)
        session.bound_audience_id = bindings.get("audience_package_id")
        session.bound_targeting_id = bindings.get("targeting_package_id")

        if session.selected_product is not None:
            session.selected_product.update(
                {
                    "audience_package_id": bindings.get("audience_package_id"),
                    "audience_package_name": bindings.get("audience_package_name"),
                    "targeting_package_id": bindings.get("targeting_package_id"),
                    "targeting_package_name": bindings.get("targeting_package_name"),
                }
            )

        creatives = await recommend_creatives(product_id)
        preselected = [c.get("creative_id") for c in creatives[:3] if c.get("creative_id")]
        session.selected_creative_ids = [str(cid) for cid in preselected]
        session.state = SessionState.CREATIVE_SELECTION

        msg1 = "商品已选择。第二步：请确认宣传视频（可增删），完成后输入“下一步”。"
        msg2 = "为您推荐以下宣传视频："
        session.add_message("assistant", msg1)
        session.add_message("assistant", msg2, MessageType.CREATIVE_CARDS)

        return SkillResult(
            handled=True,
            messages=[
                {"type": MessageType.TEXT, "content": msg1},
                {
                    "type": MessageType.CREATIVE_CARDS,
                    "content": msg2,
                    "creatives": creatives,
                    "selected_ids": session.selected_creative_ids,
                },
            ],
        )

    async def handle_update_creatives(self, session: Session, creative_ids: list[str]) -> SkillResult:
        session.selected_creative_ids = creative_ids
        return SkillResult(handled=True)

    async def _search_products_step(self, session: Session, text: str) -> SkillResult:
        parsed = await parse_slots(text, session.slots)
        session.slots = parsed

        keyword = parsed.vehicle.value if parsed.vehicle else text
        session.product_keyword = keyword
        session.state = SessionState.PRODUCT_SEARCH

        result = await search_products(str(keyword))
        products = result.get("products", [])

        if not products:
            msg = result.get("guidance") or "未找到相关商品，请更换关键词。"
            session.add_message("assistant", msg)
            return SkillResult(handled=True, messages=[{"type": MessageType.TEXT, "content": msg}])

        tip = "第一步：请先选择要推广的商品。"
        card_msg = "为您找到以下商品，请选择："
        session.add_message("assistant", tip)
        session.add_message("assistant", card_msg, MessageType.PRODUCT_CARDS)
        return SkillResult(
            handled=True,
            messages=[
                {"type": MessageType.TEXT, "content": tip},
                {
                    "type": MessageType.PRODUCT_CARDS,
                    "content": card_msg,
                    "products": products,
                },
            ],
        )

    def _next_slot_prompt(self, session: Session) -> Optional[str]:
        for field in _REQUIRED_ORDER:
            slot = getattr(session.slots, field)
            if slot is None:
                return _FIELD_PROMPTS[field]
            source = slot.source or ""
            if source.startswith("默认"):
                return f"当前{self._field_label(field)}使用默认值，请您确认或修改。{_FIELD_PROMPTS[field]}"
        return None

    def _build_plan_confirm_messages(self, session: Session) -> list[dict[str, Any]]:
        session.state = SessionState.PREVIEW
        plan_data = _build_plan_confirm_data(session)
        tip = "已完成全部配置。最后一步：请确认计划并点击「确认推送至巨量引擎」。"
        card_msg = "巨量本地推·计划参数确认"
        session.add_message("assistant", tip)
        session.add_message("assistant", card_msg, MessageType.PLAN_CONFIRM_CARD)
        return [
            {"type": MessageType.TEXT, "content": tip},
            {
                "type": MessageType.PLAN_CONFIRM_CARD,
                "content": card_msg,
                "plan_confirm": plan_data,
            },
        ]

    def _should_return_welcome(self, text: str) -> bool:
        normalized = text.strip().lower()
        if not normalized:
            return False

        if any(keyword in normalized for keyword in _CAMPAIGN_KEYWORDS):
            return False

        return any(pattern.search(text) for pattern in _GENERAL_HELP_PATTERNS)

    def _field_label(self, field: str) -> str:
        labels = {
            "scene": "营销场景",
            "goal": "营销目标",
            "location": "投放地域",
            "audience": "投放人群",
            "budget": "预算",
            "bid_strategy": "出价策略",
            "schedule": "排期",
        }
        return labels.get(field, field)


def slots_summary(session: Session) -> dict[str, Any]:
    s = session.slots
    return {
        "vehicle": s.vehicle.value if s.vehicle else None,
        "scene": s.scene.value if s.scene else None,
        "goal": s.goal.value if s.goal else None,
        "location": s.location.value if s.location else None,
        "budget": s.budget.value if s.budget else None,
        "bid_strategy": s.bid_strategy.value if s.bid_strategy else None,
        "schedule": s.schedule.value if s.schedule else None,
        "audience": s.audience.value if s.audience else None,
    }


def _format_location(location: Any) -> str:
    if not isinstance(location, dict):
        return "同城"
    t = location.get("type")
    if t == "radius":
        km = location.get("km") or 5
        return f"周边{km}公里"
    if t == "nationwide":
        return "全国"
    return "同城"


def _format_scene(scene: Any) -> str:
    if scene == "short_video":
        return "短视频"
    if scene == "live":
        return "直播"
    return ""


def _format_goal(goal: Any) -> str:
    if goal == "store_traffic":
        return "门店引流"
    if goal == "test_drive":
        return "试驾预约"
    if goal == "lead_collection":
        return "线索收集"
    return ""


def _format_bid(bid: Any) -> str:
    if not isinstance(bid, dict):
        return "智能出价"
    if bid.get("type") == "manual":
        amount = bid.get("amount")
        return f"手动出价({amount}元)" if amount else "手动出价"
    return "智能出价"


def _format_schedule(schedule: Any) -> str:
    if not isinstance(schedule, dict):
        return "7天"
    days = schedule.get("days", 7)
    slot_names = {
        "morning": "早间",
        "evening": "晚间",
        "all_day": "全天",
    }
    time_slots = schedule.get("time_slots") or []
    if isinstance(time_slots, list) and time_slots:
        ts_desc = "、".join(slot_names.get(ts, str(ts)) for ts in time_slots)
    else:
        ts_desc = "全天"
    return f"{days}天（{ts_desc}）"


def _format_audience(audience: Any) -> dict[str, str]:
    if not isinstance(audience, dict):
        return {}

    result: dict[str, str] = {}
    gender_map = {"male": "男性", "female": "女性", "both": "不限"}
    gender = audience.get("gender")
    if gender in gender_map:
        result["性别"] = gender_map[gender]

    age_range = audience.get("age_range")
    if isinstance(age_range, str) and age_range.strip():
        result["年龄"] = f"{age_range}岁"

    return result


def _build_plan_confirm_data(session: Session) -> dict[str, Any]:
    scene_val = session.slots.scene.value if session.slots.scene else None
    goal_val = session.slots.goal.value if session.slots.goal else None
    location_val = session.slots.location.value if session.slots.location else None
    bid_val = session.slots.bid_strategy.value if session.slots.bid_strategy else None
    schedule_val = session.slots.schedule.value if session.slots.schedule else None
    audience_val = session.slots.audience.value if session.slots.audience else None

    return {
        "vehicle": str(session.slots.vehicle.value) if session.slots.vehicle else "",
        "scene": _format_scene(scene_val),
        "goal": _format_goal(goal_val),
        "location": _format_location(location_val),
        "budget": session.slots.budget.value if session.slots.budget else 0,
        "bid_strategy": _format_bid(bid_val),
        "schedule": _format_schedule(schedule_val),
        "audience": _format_audience(audience_val),
        "product_id": session.selected_product_id or "",
        "product_name": session.selected_product.get("product_name") if session.selected_product else "",
    }
