from __future__ import annotations

from typing import Any

from app.models.session import MessageType, Session
from app.nlp.parser import parse_slots_with_intent
from app.services.llm_chat_service import chat_with_llm
from app.skills.automotive_marketing import AutomotiveMarketingSkill, slots_summary


class SkillOrchestrator:
    def __init__(self):
        self.automotive_skill = AutomotiveMarketingSkill()

    async def route_message(self, session: Session, text: str) -> list[dict[str, Any]]:
        if await self.automotive_skill.can_handle(session, text):
            session.active_skill = self.automotive_skill.name
            result = await self.automotive_skill.handle_message(session, text)
            if result.handled:
                return result.messages

        if await self._should_activate_automotive_skill(session, text):
            session.active_skill = self.automotive_skill.name
            result = await self.automotive_skill.handle_message(session, text)
            if result.handled:
                return result.messages

        # 主工程保留通用 LLM 对话能力
        session.active_skill = None
        answer = await chat_with_llm(session, text)
        session.add_message("assistant", answer)
        return [{"type": MessageType.TEXT, "content": answer}]

    async def _should_activate_automotive_skill(self, session: Session, text: str) -> bool:
        if session.active_skill == self.automotive_skill.name:
            return True

        probe_slots, intent = await parse_slots_with_intent(text, session.slots)
        if intent not in {"isCreate", "isModify", "isConfirm"}:
            return False

        return self._has_any_slot_value(probe_slots)

    def _has_any_slot_value(self, slots: Any) -> bool:
        for field in self.automotive_skill.required_slots_order:
            if getattr(slots, field, None) is not None:
                return True
        return False

    async def select_product(self, session: Session, product_id: str, product: dict[str, Any]) -> list[dict[str, Any]]:
        if session.active_skill == self.automotive_skill.name:
            result = await self.automotive_skill.handle_select_product(session, product_id, product)
            if result.handled:
                return result.messages
        msg = "当前会话未启用商品选择能力，请先描述投放需求。"
        session.add_message("assistant", msg)
        return [{"type": MessageType.ERROR, "content": msg}]

    async def update_creatives(self, session: Session, creative_ids: list[str]) -> None:
        if session.active_skill == self.automotive_skill.name:
            await self.automotive_skill.handle_update_creatives(session, creative_ids)
            return
        session.selected_creative_ids = creative_ids

    def slots_summary(self, session: Session) -> dict[str, Any]:
        if session.active_skill == self.automotive_skill.name or session.selected_product_id:
            return slots_summary(session)
        return slots_summary(session)


_orchestrator: SkillOrchestrator | None = None


def get_skill_orchestrator() -> SkillOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SkillOrchestrator()
    return _orchestrator
