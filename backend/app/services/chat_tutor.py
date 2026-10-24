"""AI 讲题服务：上下文组装 + 流式讲解 + 消息持久化。

上下文工程要点：
- 系统提示限定"基于给定资料讲解，不编造"
- 注入题目完整信息（题干/选项/标准答案/解析/难度）
- 注入关联资料原文（出题来源块优先，同资料其他块补充）
- 注入考生最近一次作答（让讲解更有针对性）
"""

from datetime import datetime

from ..models import AIChatMessage, AIChatSession, ExamAnswer, ExamSession, Question
from ..services.runtime import get_llm

TUTOR_SYSTEM_PROMPT = """你是一位耐心严谨的技术面试辅导老师。学生正在请教一道面试题，你需要：

1. 只基于下方给出的「题目资料」进行讲解，不编造资料中没有的信息
2. 先直接回答核心结论，再展开推导过程
3. 如果学生给出了自己的答案，针对性点评对错与遗漏
4. 使用 Markdown 格式，适当使用代码块、列表；语言简洁，不堆砌废话
5. 资料不足以回答时，明确说"根据现有资料无法确定"，并建议学生查阅什么"""


def build_tutor_messages(db, question: Question, history: list[AIChatMessage], user_id: int) -> list[dict]:
    """组装讲题请求的 messages（系统提示 + 上下文 + 历史 + 最后一条用户消息）。"""
    # 题目信息
    question_block = (
        f"【题目】（{question.q_type}，难度 {question.difficulty}）\n{question.content}\n"
    )
    if question.options:
        question_block += "选项：\n" + "\n".join(question.options) + "\n"
    question_block += f"标准答案：{question.answer}\n解析：{question.explanation}\n"

    # 关联资料原文：出题来源块优先
    source_texts: list[str] = []
    if question.chunk_id is not None:
        from ..models import KnowledgeChunk

        chunk = db.get(KnowledgeChunk, question.chunk_id)
        if chunk is not None:
            source_texts.append(f"[出处] {chunk.content}")
    if question.entry_id is not None:
        from ..models import KnowledgeChunk

        siblings = (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.entry_id == question.entry_id,
                KnowledgeChunk.id != question.chunk_id,
            )
            .limit(2)
            .all()
        )
        for sib in siblings:
            source_texts.append(f"[相关] {sib.content}")

    # 考生最近一次作答（针对性点评）
    last_answer = (
        db.query(ExamAnswer)
        .join(ExamSession, ExamSession.id == ExamAnswer.session_id)
        .filter(
            ExamAnswer.question_id == question.id,
            ExamSession.user_id == user_id,
            ExamAnswer.user_answer != "",
        )
        .order_by(ExamAnswer.id.desc())
        .first()
    )
    answer_block = ""
    if last_answer is not None:
        answer_block = f"\n【学生最近一次作答】{last_answer.user_answer}（得分 {last_answer.score}/{last_answer.max_score}）"

    context = (
        "以下是讲解所需的资料：\n\n"
        f"{question_block}\n{answer_block}\n"
        "【题目资料】\n" + ("\n---\n".join(source_texts) if source_texts else "（无关联资料，基于通识讲解）")
    )

    messages = [{"role": "system", "content": TUTOR_SYSTEM_PROMPT + "\n\n" + context}]
    for msg in history:
        if msg.role in ("user", "assistant") and msg.content:
            messages.append({"role": msg.role, "content": msg.content})
    return messages


def stream_tutor_reply(db, session: AIChatSession, user_content: str):
    """流式生成讲解内容；结束后把完整回复落库。yield 文本增量。"""
    question = db.get(Question, session.question_id)
    if question is None:
        raise RuntimeError("题目不存在")

    # 用户消息落库
    user_message = AIChatMessage(session_id=session.id, role="user", content=user_content)
    db.add(user_message)
    db.commit()
    db.refresh(session)

    history = [m for m in session.messages if m.id != user_message.id]
    messages = build_tutor_messages(db, question, history, session.user_id)

    llm = get_llm()
    parts: list[str] = []
    try:
        for chunk in llm.chat_stream(messages, temperature=0.4, max_tokens=2000):
            parts.append(chunk)
            yield chunk
    except Exception as exc:  # noqa: BLE001 - 透传给 SSE error 事件
        # 已产生的部分内容仍然保存，避免学生看不到半截讲解
        if parts:
            _persist_assistant(db, session, "".join(parts))
        raise RuntimeError(f"AI 讲解失败：{exc}") from exc

    _persist_assistant(db, session, "".join(parts))


def _persist_assistant(db, session: AIChatSession, content: str) -> None:
    if not content.strip():
        return
    db.add(AIChatMessage(session_id=session.id, role="assistant", content=content))
    session.updated_at = datetime.utcnow()
    db.commit()
