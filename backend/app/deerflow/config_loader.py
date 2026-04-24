"""DeerFlow 流程配置加载器。

从 YAML 文件中加载流程图定义，并提供条件求值与节点解析功能。
新增技能只需添加对应的 YAML 文件，无需修改此模块。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.models.session import Session, SessionState


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class NodeDef:
    """单个流程节点的定义。"""
    action: str          # 对应注册到引擎的 handler 名称
    description: str = ""


@dataclass
class RoutingRule:
    """一条路由规则：满足 condition 则进入 node。"""
    condition: dict[str, Any]
    node: str


@dataclass
class FlowConfig:
    """完整的流程配置，对应一个 YAML 文件。"""
    skill: str
    entry_keywords: list[str] = field(default_factory=list)
    confirm_texts: list[str] = field(default_factory=list)
    required_slots_order: list[str] = field(default_factory=list)
    slot_prompts: dict[str, str] = field(default_factory=dict)
    routing_rules: list[RoutingRule] = field(default_factory=list)
    nodes: dict[str, NodeDef] = field(default_factory=dict)


# ── 加载 ──────────────────────────────────────────────────────────────────────

def load_flow_config(path: str | Path) -> FlowConfig:
    """从 YAML 文件加载 FlowConfig。"""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    nodes = {
        k: NodeDef(
            action=v["action"],
            description=v.get("description", ""),
        )
        for k, v in data.get("nodes", {}).items()
    }

    rules = [
        RoutingRule(condition=r["condition"], node=r["node"])
        for r in data.get("routing_rules", [])
    ]

    return FlowConfig(
        skill=data["skill"],
        entry_keywords=data.get("entry_keywords", []),
        confirm_texts=data.get("confirm_texts", []),
        required_slots_order=data.get("required_slots_order", []),
        slot_prompts=data.get("slot_prompts", {}),
        routing_rules=rules,
        nodes=nodes,
    )


# ── 条件求值 ──────────────────────────────────────────────────────────────────

def _evaluate_condition(cond: dict[str, Any], session: Session) -> bool:
    """
    对单条条件求值。支持的 type：

    - ``always``       — 无条件为 True（兜底）
    - ``field_set``    — ``session.<field>`` 为真值
    - ``field_not_set``— ``session.<field>`` 为假值/None
    - ``state_is``     — ``session.state == SessionState(state)``
    - ``state_in``     — ``session.state in {SessionState(s) for s in states}``
    """
    ctype = cond.get("type", "always")

    if ctype == "always":
        return True

    if ctype == "field_set":
        return bool(getattr(session, cond["field"], None))

    if ctype == "field_not_set":
        return not bool(getattr(session, cond["field"], None))

    if ctype == "state_is":
        try:
            return session.state == SessionState(cond["state"])
        except ValueError:
            return False

    if ctype == "state_in":
        try:
            target_states = {SessionState(s) for s in cond.get("states", [])}
        except ValueError:
            return False
        return session.state in target_states

    return False


def resolve_node(config: FlowConfig, session: Session) -> str:
    """按路由规则顺序求值，返回第一个匹配节点名。"""
    for rule in config.routing_rules:
        if _evaluate_condition(rule.condition, session):
            return rule.node
    return "fallback"
