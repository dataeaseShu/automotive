from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from app.deerflow.config_loader import load_flow_config
from app.models.session import MessageType, Session, SessionState
from app.models.slots import SlotField
from app.nlp.parser import parse_slots_with_intent
from app.services.plan_service import submit_plan
from app.services.product_service import search_products
from app.skills.base import Skill, SkillResult

_GENERAL_HELP_PATTERNS = [
    re.compile(r"^(你好|您好|嗨|hi|hello)[!！?？]?$", re.IGNORECASE),
    re.compile(r"你是谁|你是干什么的|你能做什么|介绍一下你自己|自我介绍"),
    re.compile(r"怎么用|如何使用|帮助|使用说明|功能介绍"),
]

# YAML 配置文件路径：backend/data/flows/automotive_marketing.yaml
_FLOW_CONFIG_PATH = (
    Path(__file__).parent.parent.parent / "data" / "flows" / "automotive_marketing.yaml"
)


class AutomotiveMarketingSkill(Skill):
    name = "automotive_marketing"
    _VEHICLE_FALLBACK_KEYWORDS = ["比亚迪", "特斯拉", "理想", "宝马", "奔驰"]

    def __init__(self) -> None:
        self.flow = load_flow_config(_FLOW_CONFIG_PATH)
        self.required_slots_order = list(self.flow.required_slots_order)

    async def can_handle(self, session: Session, text: str) -> bool:
        if session.active_skill == self.name:
            return True
        if session.state in {
            SessionState.SLOT_FILLING,
            SessionState.PREVIEW,
        }:
            return True
        normalized = text.strip().lower()
        return any(keyword in normalized for keyword in self.flow.entry_keywords)

    async def handle_message(self, session: Session, text: str) -> SkillResult:
        reply_messages: list[dict[str, Any]] = []

        if self._should_return_welcome(text) and session.active_skill != self.name:
            welcome = (
                "您好！我是智能投手 Lumax。\n"
                "我会先识别您的投放意图并提取已提供的信息，再按缺失槽位顺序追问，最后直接生成完整投放计划。"
            )
            session.add_message("assistant", welcome)
            reply_messages.append({"type": MessageType.TEXT, "content": welcome})
            return SkillResult(handled=True, messages=reply_messages)

        if text in self.flow.confirm_texts:
            if session.state != SessionState.PREVIEW:
                msg = "计划信息还未补全，请先按顺序完成缺失槽位填写。"
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

        pending = self._current_pending_slot(session)
        session.slots, intent = await parse_slots_with_intent(text, session.slots, pending_slot=pending)

        if intent in {"isCreate", "isModify", "isConfirm"}:
            session.active_skill = self.name

        vehicle_card_result = await self._maybe_offer_vehicle_cards(session, text)
        if vehicle_card_result is not None:
            return vehicle_card_result

        next_prompt = self._next_slot_prompt(session)
        if next_prompt:
            session.state = SessionState.SLOT_FILLING
            session.add_message("assistant", next_prompt)
            reply_messages.append({"type": MessageType.TEXT, "content": next_prompt})
            return SkillResult(handled=True, messages=reply_messages)

        return SkillResult(handled=True, messages=self._build_plan_confirm_messages(session))

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
            source="product_card_select",
        )

        reply_messages: list[dict[str, Any]] = []
        picked_msg = f"已选择车型：{selected_vehicle}。"
        session.add_message("assistant", picked_msg)
        reply_messages.append({"type": MessageType.TEXT, "content": picked_msg})

        next_prompt = self._next_slot_prompt(session)
        if next_prompt:
            session.state = SessionState.SLOT_FILLING
            session.add_message("assistant", next_prompt)
            reply_messages.append({"type": MessageType.TEXT, "content": next_prompt})
            return SkillResult(handled=True, messages=reply_messages)

        return SkillResult(handled=True, messages=reply_messages + self._build_plan_confirm_messages(session))

    async def handle_update_creatives(self, session: Session, creative_ids: list[str]) -> SkillResult:
        session.selected_creative_ids = creative_ids
        return SkillResult(handled=True)

    def _current_pending_slot(self, session: Session) -> Optional[str]:
        missing = session.slots.missing_required(order=self.required_slots_order)
        return missing[0] if missing else None

    def _next_slot_prompt(self, session: Session) -> Optional[str]:
        pending = self._current_pending_slot(session)
        if pending is None:
            return None
        return self.flow.slot_prompts.get(pending, f"请补充{self._field_label(pending)}。")

    def _build_plan_confirm_messages(self, session: Session) -> list[dict[str, Any]]:
        session.state = SessionState.PREVIEW
        plan_data = _build_plan_confirm_data(session)
        tip = "已完成全部槽位填写，以下是完整投放计划。确认无误后可直接提交。"
        card_msg = "投放计划预览"
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

        if any(keyword in normalized for keyword in self.flow.entry_keywords):
            return False

        return any(pattern.search(text) for pattern in _GENERAL_HELP_PATTERNS)

    async def _maybe_offer_vehicle_cards(self, session: Session, text: str) -> Optional[SkillResult]:
        if session.slots.vehicle is not None:
            return None

        pending = self._current_pending_slot(session)
        if pending != "vehicle":
            return None

        keyword = text.strip()
        if not keyword:
            keyword = "比亚迪"

        result = await search_products(keyword)
        products = result.get("products", [])
        if not products:
            products = await self._load_fallback_vehicle_candidates(limit=10)
        if not products:
            return None

        session.product_keyword = keyword
        session.state = SessionState.PRODUCT_SEARCH

        tip = "未识别到具体车型，请从以下车型中选择（最多10个）。"
        session.add_message("assistant", tip)
        session.add_message("assistant", "为您找到以下候选车型：", MessageType.PRODUCT_CARDS)

        messages: list[dict[str, Any]] = [{"type": MessageType.TEXT, "content": tip}]

        messages.append(
            {
                "type": MessageType.PRODUCT_CARDS,
                "content": "为您找到以下候选车型：",
                "products": products,
            }
        )
        return SkillResult(handled=True, messages=messages)

    async def _load_fallback_vehicle_candidates(self, limit: int = 10) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for kw in self._VEHICLE_FALLBACK_KEYWORDS:
            result = await search_products(kw)
            for item in result.get("products", []):
                pid = str(item.get("product_id") or "")
                if not pid or pid in seen_ids:
                    continue
                merged.append(item)
                seen_ids.add(pid)
                if len(merged) >= limit:
                    return merged

        return merged

    def _field_label(self, field: str) -> str:
        labels = {
            "vehicle": "推广车型",
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
    }
