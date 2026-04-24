from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid
import time

from app.models.slots import PlanSlots


class SessionState(str, Enum):
    INIT = "init"
    SLOT_FILLING = "slot_filling"
    CLARIFYING = "clarifying"
    PRODUCT_SEARCH = "product_search"
    PRODUCT_SELECTED = "product_selected"
    CREATIVE_SELECTION = "creative_selection"
    UPLOAD_PROMPT = "upload_prompt"
    UPLOADING = "uploading"
    PREVIEW = "preview"
    SUBMITTED = "submitted"


class MessageType(str, Enum):
    TEXT = "text"
    PRODUCT_CARDS = "product_cards"
    CREATIVE_CARDS = "creative_cards"
    PREVIEW_CARD = "preview_card"
    UPLOAD_BUTTON = "upload_button"
    CONFIRM_BUTTON = "confirm_button"
    PLAN_CONFIRM_CARD = "plan_confirm_card"
    ERROR = "error"


class ChatMessage(BaseModel):
    role: str                    # "assistant" | "user"
    type: MessageType = MessageType.TEXT
    content: Any                 # str 或 结构化卡片数据
    timestamp: float = Field(default_factory=time.time)


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionState = SessionState.INIT
    active_skill: Optional[str] = None
    slots: PlanSlots = Field(default_factory=PlanSlots)
    messages: List[ChatMessage] = Field(default_factory=list)

    # 当前待追问的槽位队列
    pending_clarifications: List[str] = Field(default_factory=list)

    # 商品选择
    product_keyword: Optional[str] = None
    selected_product_id: Optional[str] = None
    selected_product: Optional[Dict[str, Any]] = None
    bound_audience_id: Optional[str] = None
    bound_targeting_id: Optional[str] = None

    # 成片选择（最多10个）
    recommended_creative_ids: List[str] = Field(default_factory=list)
    selected_creative_ids: List[str] = Field(default_factory=list)

    # 上传素材（最多10个，加入候选后可勾选）
    uploaded_material_ids: List[str] = Field(default_factory=list)

    # 最终计划草稿
    plan_draft: Optional[Dict[str, Any]] = None
    plan_id: Optional[str] = None

    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()

    def add_message(self, role: str, content: Any,
                    msg_type: MessageType = MessageType.TEXT) -> None:
        self.messages.append(ChatMessage(role=role, type=msg_type, content=content))
        self.touch()

    def total_creatives(self) -> int:
        """已选成片数（推荐选中 + 上传选中）"""
        return len(self.selected_creative_ids)
