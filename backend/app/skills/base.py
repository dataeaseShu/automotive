from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.session import Session


@dataclass
class SkillResult:
    handled: bool
    messages: list[dict[str, Any]] = field(default_factory=list)


class Skill:
    name: str = "base"

    async def can_handle(self, session: Session, text: str) -> bool:
        raise NotImplementedError

    async def handle_message(self, session: Session, text: str) -> SkillResult:
        raise NotImplementedError

    async def handle_select_product(self, session: Session, product_id: str, product: dict[str, Any]) -> SkillResult:
        return SkillResult(handled=False)

    async def handle_update_creatives(self, session: Session, creative_ids: list[str]) -> SkillResult:
        return SkillResult(handled=False)
