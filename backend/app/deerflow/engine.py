"""DeerFlow 可配置流程引擎。

节点定义与路由规则均来自 FlowConfig（YAML），引擎本身不包含任何业务逻辑。
新增技能步骤：
  1. 在 data/flows/ 下新建 YAML 配置文件；
  2. 创建对应 Skill 类，调用 engine.register() 注册 action handler；
  3. 无需修改此文件。
"""
from __future__ import annotations

from typing import Awaitable, Callable

from app.deerflow.config_loader import FlowConfig, resolve_node
from app.models.session import Session
from app.skills.base import SkillResult

FlowHandler = Callable[[Session, str], Awaitable[SkillResult]]


class DeerFlowEngine:
    """配置驱动的流程路由器。

    路由规则、节点→action 映射均从 FlowConfig 读取；
    具体 action handler 由 Skill 通过 register() 注入。
    """

    def __init__(self, config: FlowConfig) -> None:
        self._config = config
        self._handlers: dict[str, FlowHandler] = {}

    # ── 公开 API ──────────────────────────────────────────────────────────────

    def register(self, action_name: str, handler: FlowHandler) -> None:
        """注册 action handler，action_name 需与 YAML nodes.<node>.action 对应。"""
        self._handlers[action_name] = handler

    async def route(self, session: Session, text: str) -> SkillResult:
        """根据 session 状态解析当前节点，调度到对应 handler。"""
        node_name = resolve_node(self._config, session)
        node = self._config.nodes.get(node_name)
        if node is None:
            return SkillResult(handled=False)

        handler = self._handlers.get(node.action)
        if handler is None:
            # 兜底：尝试 fallback handler
            fallback_node = self._config.nodes.get("fallback")
            if fallback_node:
                handler = self._handlers.get(fallback_node.action)
            if handler is None:
                return SkillResult(handled=False)

        return await handler(session, text)

    # ── 只读属性（供 Skill 使用）─────────────────────────────────────────────

    @property
    def entry_keywords(self) -> list[str]:
        return self._config.entry_keywords

    @property
    def confirm_texts(self) -> set[str]:
        return set(self._config.confirm_texts)

    @property
    def required_slots_order(self) -> list[str]:
        return self._config.required_slots_order

    @property
    def slot_prompts(self) -> dict[str, str]:
        return self._config.slot_prompts

    @property
    def config(self) -> FlowConfig:
        return self._config
