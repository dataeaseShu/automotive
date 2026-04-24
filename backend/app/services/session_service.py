"""
会话状态管理服务（内存存储，MVP版本）
- create / get / update / delete 会话
- 封装状态迁移逻辑
"""
import time
from typing import Optional

from app.models.session import Session, SessionState
from app.config import get_settings

_sessions: dict[str, Session] = {}


def create_session() -> Session:
    s = Session()
    _sessions[s.session_id] = s
    return s


def get_session(session_id: str) -> Optional[Session]:
    s = _sessions.get(session_id)
    if s is None:
        return None
    settings = get_settings()
    if time.time() - s.updated_at > settings.SESSION_TTL:
        del _sessions[session_id]
        return None
    return s


def save_session(session: Session) -> None:
    session.touch()
    _sessions[session.session_id] = session


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def transition(session: Session, new_state: SessionState) -> Session:
    session.state = new_state
    session.touch()
    return session
