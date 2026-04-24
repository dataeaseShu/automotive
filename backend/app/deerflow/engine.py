from __future__ import annotations

from typing import Awaitable, Callable

from app.models.session import Session
from app.skills.base import SkillResult

FlowHandler = Callable[[Session, str], Awaitable[SkillResult]]


class DeerFlowEngine:
    """A lightweight deerFlow-style stage router.

    It maps stage keys to async handlers and routes a message by stage.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, FlowHandler] = {}

    def register(self, stage: str, handler: FlowHandler) -> None:
        self._handlers[stage] = handler

    async def route(self, stage: str, session: Session, text: str) -> SkillResult:
        handler = self._handlers.get(stage)
        if handler is None:
            fallback = self._handlers.get("fallback")
            if fallback is None:
                return SkillResult(handled=False)
            return await fallback(session, text)
        return await handler(session, text)
