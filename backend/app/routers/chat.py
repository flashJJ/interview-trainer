"""AI 讲题路由：会话管理 + SSE 流式讲解。"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import AIChatMessage, AIChatSession, Question, User
from ..schemas import (
    ChatMessageOut,
    ChatSessionOut,
    CreateChatSessionIn,
    SendChatMessageIn,
)
from ..services.runtime import get_llm

router = APIRouter(prefix="/chat", tags=["chat"])


def _session_out(session: AIChatSession) -> ChatSessionOut:
    return ChatSessionOut(
        id=session.id,
        question_id=session.question_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _message_out(msg: AIChatMessage) -> ChatMessageOut:
    return ChatMessageOut(id=msg.id, role=msg.role, content=msg.content, created_at=msg.created_at)


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = (
        db.query(AIChatSession)
        .filter(
            AIChatSession.user_id == current_user.id,
            AIChatSession.question_id == question_id,
        )
        .order_by(AIChatSession.id.desc())
        .limit(20)
        .all()
    )
    return [_session_out(s) for s in sessions]


@router.post("/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: CreateChatSessionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = db.get(Question, payload.question_id)
    if question is None or question.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    session = AIChatSession(
        user_id=current_user.id,
        question_id=payload.question_id,
        title=question.content[:50],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(session)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.get(AIChatSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return [_message_out(m) for m in session.messages]


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: int,
    payload: SendChatMessageIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送消息并以 SSE 流式返回讲解内容。

    事件格式（data 行为 JSON）：
    - {"type": "chunk", "content": "..."}   文本增量
    - {"type": "done"}                      讲解完成
    - {"type": "error", "message": "..."}   失败（含已输出半截内容的情况）
    """
    session = db.get(AIChatSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    content = payload.content.strip()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "消息内容不能为空")
    if len(content) > 2000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "消息内容过长（上限 2000 字符）")
    if not get_llm().enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "LLM 未配置，请先在系统配置页填写 API Key",
        )

    from ..services.chat_tutor import stream_tutor_reply

    def event_stream():
        try:
            for chunk in stream_tutor_reply(db, session, content):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001 - 错误也走 SSE 事件，前端统一处理
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
