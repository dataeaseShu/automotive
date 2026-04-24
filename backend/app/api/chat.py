"""
对话流核心路由
- 主工程仅保留 LLM 对话入口
- 业务能力通过 skill 编排器调用
POST /api/chat/start
POST /api/chat/message
GET  /api/chat/{session_id}/state
"""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import session_service
from app.services.skill_orchestrator import get_skill_orchestrator

router = APIRouter(prefix="/api/chat", tags=["chat"])

WELCOME_MESSAGE = (
    "您好！我是 Lumax 对话助手。\n"
    "您可以直接聊天，或描述汽车投放需求（例如：理想L7、直播、同城、门店引流、10万预算）。"
)


class StartResponse(BaseModel):
    session_id: str
    message: str


class MessageRequest(BaseModel):
    session_id: str
    message: str


class MessageResponse(BaseModel):
    session_id: str
    state: str
    messages: list[dict[str, Any]]
    slots_summary: dict[str, Any]


class SelectProductRequest(BaseModel):
    session_id: str
    product_id: str
    product: dict[str, Any]


class UpdateCreativesRequest(BaseModel):
    session_id: str
    creative_ids: list[str]


@router.post("/start", response_model=StartResponse)
async def start_chat():
    session = session_service.create_session()
    session.add_message("assistant", WELCOME_MESSAGE)
    session_service.save_session(session)
    return StartResponse(session_id=session.session_id, message=WELCOME_MESSAGE)


@router.post("/message", response_model=MessageResponse)
async def send_message(req: MessageRequest):
    session = session_service.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期，请重新开始")

    text = req.message.strip()
    session.add_message("user", text)

    orchestrator = get_skill_orchestrator()
    reply_messages = await orchestrator.route_message(session, text)

    session_service.save_session(session)
    return MessageResponse(
        session_id=session.session_id,
        state=session.state.value,
        messages=reply_messages,
        slots_summary=orchestrator.slots_summary(session),
    )


@router.get("/{session_id}/state")
async def get_state(session_id: str):
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    orchestrator = get_skill_orchestrator()
    return {
        "session_id": session_id,
        "state": session.state.value,
        "slots_summary": orchestrator.slots_summary(session),
        "selected_product": session.selected_product,
        "selected_creatives_count": session.total_creatives(),
        "active_skill": session.active_skill,
    }


@router.post("/select-product", response_model=MessageResponse)
async def select_product(req: SelectProductRequest):
    session = session_service.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    orchestrator = get_skill_orchestrator()
    reply_messages = await orchestrator.select_product(session, req.product_id, req.product)

    session_service.save_session(session)
    return MessageResponse(
        session_id=session.session_id,
        state=session.state.value,
        messages=reply_messages,
        slots_summary=orchestrator.slots_summary(session),
    )


@router.post("/update-creatives")
async def update_creatives(req: UpdateCreativesRequest):
    session = session_service.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    orchestrator = get_skill_orchestrator()
    await orchestrator.update_creatives(session, req.creative_ids)
    session_service.save_session(session)
    return {"session_id": session.session_id, "selected_count": len(req.creative_ids)}
