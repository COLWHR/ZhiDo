from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.crud import (
    add_team_members,
    create_team,
    delete_team,
    get_persona,
    get_team,
    get_team_messages,
    list_decision_logs,
    list_teams,
    log_decision,
    remove_team_member,
    save_team_message,
)
from app.decision import router as decision_router
from app.db.session import get_db
from app.schemas import (
    TeamAddMembers,
    TeamChatRequest,
    TeamCreate,
)
from app.services import credit_service, team_orchestrator
from app.services.skill_runtime import (
    build_llm_messages,
    render_csv_artifact,
    render_png_artifact,
    render_text_artifact,
)
from utils import LLMServiceError, get_chat_completion

logger = logging.getLogger(__name__)

router = APIRouter()

# Only keep the most recent N messages in the prompt to avoid blowing up the
# model context window as the group chat grows.
MAX_CONTEXT_MESSAGES = 20

# Conservative placeholder output used when pre-checking credits for N agents.
PRECHECK_OUTPUT_CHARS = 300

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def _stream_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _count_vision_images(messages: List[Dict[str, Any]]) -> int:
    count = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    count += 1
    return count


def _messages_plain_text(messages: List[Dict[str, Any]]) -> str:
    chunks: List[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            chunks.append(content)
    return "\n".join(chunks)


def _chunk_content(chunk: Any, use_vision: bool = False) -> str:
    if chunk is None:
        return ""
    if use_vision and isinstance(chunk, dict):
        choices = chunk.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        return str(delta.get("content") or "")
    choices = getattr(chunk, "choices", None)
    if not choices:
        return ""
    try:
        delta = choices[0].delta
        return str(getattr(delta, "content", "") or "")
    except Exception:
        return ""


def _inject_knowledge(db: Any, persona_id: Optional[int], messages: List[Dict[str, Any]]) -> None:
    from app.crud import build_knowledge_block

    if not persona_id:
        return
    try:
        block = build_knowledge_block(db, int(persona_id))
    except Exception as exc:
        logger.warning("Failed to load persona knowledge: %s", exc)
        return
    if not block:
        return
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = (
            f"{messages[0].get('content') or ''}\n\n"
            "【你可参考的专属知识库】\n"
            f"{block}\n\n"
            "回答时优先依据以上知识库资料；若资料中没有相关信息，再依靠你的通用知识作答，不要编造资料里没有的内容。"
        )


def _decide_artifact_type(user_text: str, route: Dict[str, Any]) -> Optional[str]:
    """Decide whether this turn should attach a locally generated artifact.

    Route hint from the skill router wins; otherwise fall back to lightweight
    keyword matching on the user's own request. Returns None for a text-only
    reply, or one of ``docx`` / ``csv`` / ``png``.
    """
    if route.get("should_generate_artifact"):
        return str(route.get("artifact_type") or "docx").lower()

    text = str(user_text or "")
    if re.search(r"(示意图|配图|插画|画一张|流程图|思维导图|结构图|海报图)", text):
        return "png"
    if re.search(r"(表格|清单|对比表|统计表|数据汇总|排班表)", text):
        return "csv"
    if re.search(r"(文档|报告|方案|总结|论文|讲稿|手册|说明书|纪要)", text):
        return "docx"
    return None


def _build_generated_artifact(artifact_type: str, title: str, text: str) -> Dict[str, Any]:
    """Render a local artifact and normalize it to the message attachment shape."""
    artifact_type = (artifact_type or "docx").lower()
    if artifact_type in {"csv", "sheet"}:
        file_name, mime_type, storage_url = render_csv_artifact([{"content": text}], title=title)
        kind = "file"
    elif artifact_type in {"png", "image"}:
        file_name, mime_type, storage_url = render_png_artifact(text, title=title)
        kind = "image"
    else:
        file_name, mime_type, storage_url = render_text_artifact(text, title=title)
        kind = "file"

    return {
        "id": None,
        "file_name": file_name,
        "mime_type": mime_type,
        "kind": kind,
        "storage_url": storage_url,
        "preview_url": storage_url,
        "size": None,
        "meta": {"source": "generated", "artifact_type": artifact_type},
    }


def _ensure_access(db: Any, team_id: int, current_user: Any) -> Any:
    team = get_team(db, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="团队不存在")
    if current_user.role not in {"admin", "god"} and getattr(team, "owner_id", None) != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该团队")
    return team


def _persona_visible(db: Any, persona_id: int, current_user: Any) -> Any:
    persona = get_persona(db, persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"智能体 {persona_id} 不存在")
    is_owner = getattr(persona, "owner_id", None) == current_user.id
    is_public = bool(getattr(persona, "is_public", False))
    if current_user.role in {"admin", "god"} or is_owner or is_public:
        return persona
    raise HTTPException(status_code=403, detail=f"无权选择智能体 {persona_id}")


@router.get("/")
def list_my_teams(db: Any = Depends(get_db), current_user: Any = Depends(get_current_user)):
    teams = list_teams(db, current_user.id)
    return [_team_to_dict(team) for team in teams]


@router.post("/")
def create_new_team(
    payload: TeamCreate,
    db: Any = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="团队名称不能为空")
    unique_pids = list(dict.fromkeys(int(pid) for pid in (payload.persona_ids or [])))
    if not unique_pids:
        raise HTTPException(status_code=400, detail="请至少选择一位成员")
    for pid in unique_pids:
        _persona_visible(db, pid, current_user)
    team = create_team(db, current_user.id, payload.name.strip(), payload.description or "", unique_pids)
    return _team_to_dict(team)


@router.get("/{team_id}")
def get_team_detail(team_id: int, db: Any = Depends(get_db), current_user: Any = Depends(get_current_user)):
    team = _ensure_access(db, team_id, current_user)
    return _team_to_dict(team)


@router.delete("/{team_id}")
def remove_team(team_id: int, db: Any = Depends(get_db), current_user: Any = Depends(get_current_user)):
    _ensure_access(db, team_id, current_user)
    success = delete_team(db, team_id)
    return {"success": success}


@router.post("/{team_id}/members")
def add_members(
    team_id: int,
    payload: TeamAddMembers,
    db: Any = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    _ensure_access(db, team_id, current_user)
    unique_pids = list(dict.fromkeys(int(pid) for pid in (payload.persona_ids or [])))
    for pid in unique_pids:
        _persona_visible(db, pid, current_user)
    team = add_team_members(db, team_id, unique_pids)
    return _team_to_dict(team)


@router.delete("/{team_id}/members/{persona_id}")
def remove_member(
    team_id: int,
    persona_id: int,
    db: Any = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    _ensure_access(db, team_id, current_user)
    success = remove_team_member(db, team_id, persona_id)
    return {"success": success}


@router.get("/{team_id}/messages")
def list_messages(team_id: int, db: Any = Depends(get_db), current_user: Any = Depends(get_current_user)):
    _ensure_access(db, team_id, current_user)
    messages = get_team_messages(db, team_id)
    return [_message_to_dict(msg) for msg in messages]


@router.post("/{team_id}/chat/stream")
def team_chat_stream(
    team_id: int,
    payload: TeamChatRequest,
    http_request: Request,
    db: Any = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    team = _ensure_access(db, team_id, current_user)

    content = (payload.content or "").strip()
    attachments = team_orchestrator.attachments_to_dicts(payload.attachments)
    mentioned_ids = list(dict.fromkeys(int(pid) for pid in (payload.mentioned_persona_ids or [])))

    if not content and not attachments:
        raise HTTPException(status_code=400, detail="消息内容和附件不能同时为空")

    # Persist the user message first so it becomes part of the group history.
    save_team_message(
        db,
        team_id=team.id,
        sender_type="user",
        speaker_name=current_user.username,
        content=content,
        user_id=current_user.id,
        persona_id=None,
        attachments=attachments,
        mentioned_persona_ids=mentioned_ids,
        message_type="text",
    )

    members = list(getattr(team, "members", []) or [])
    resolved = team_orchestrator.resolve_mentioned_members(team, mentioned_ids)
    if not resolved:
        fallback_ids = team_orchestrator.parse_at_from_text(content, members)
        resolved = team_orchestrator.resolve_mentioned_members(team, fallback_ids)

    # No @ mention: do NOT call the LLM, just guide the user to pick a member.
    if not resolved:
        def no_mention_stream():
            yield ": connected\n\n"
            hint = "这条消息还没有 @ 群内成员。请在输入框中 @ 一位或多位成员来分配任务，未被 @ 的智能体不会自动发言。"
            save_team_message(
                db,
                team_id=team.id,
                sender_type="system",
                speaker_name="系统",
                content=hint,
                user_id=None,
                persona_id=None,
                attachments=[],
                mentioned_persona_ids=[],
                message_type="system",
            )
            yield _stream_event({"type": "system", "content": hint})
            yield "data: [DONE]\n\n"

        return StreamingResponse(no_mention_stream(), media_type="text/event-stream", headers=SSE_HEADERS)

    history = get_team_messages(db, team.id)
    context_messages = team_orchestrator.trim_context(
        team_orchestrator.history_to_context(history), MAX_CONTEXT_MESSAGES
    )

    # Pre-check credits against the assembled input, scaled for every agent that
    # will reply in this turn (each produces its own output).
    preview_persona = team_orchestrator.member_persona_dict(resolved[0])
    preview_messages, _preview_vision, _ = build_llm_messages(
        preview_persona, context_messages, attachments, base_url=str(http_request.base_url)
    )
    vision_count = _count_vision_images(preview_messages)
    input_text = _messages_plain_text(preview_messages)
    input_est = credit_service.estimate_from_text(
        db, input_text=input_text, output_text="", vision_count=vision_count
    )
    per_agent_output_est = credit_service.estimate_from_text(
        db, input_text="", output_text="x" * PRECHECK_OUTPUT_CHARS, vision_count=0
    )
    estimated_cost = input_est["cost"] + per_agent_output_est["cost"] * len(resolved)
    try:
        credit_service.check_sufficient(db, current_user.id, estimated_cost)
    except credit_service.InsufficientCreditsError as exc:
        def insufficient_stream():
            yield ": connected\n\n"
            yield _stream_event({
                "error": f"积分余额不足（当前 {exc.balance}，预计需要 {exc.required}），请联系管理员充值。",
                "kind": "insufficient_credits",
            })
            yield "data: [DONE]\n\n"

        return StreamingResponse(insufficient_stream(), media_type="text/event-stream", headers=SSE_HEADERS)

    # Three-tier intent decision: trained ML -> keyword rule -> upstream LLM.
    decision = decision_router.predict(content)
    log_decision(
        db,
        scope="team",
        reference_id=team.id,
        user_id=current_user.id,
        text=content,
        label=decision["label"],
        confidence=decision["confidence"],
        layer=decision["layer"],
        keyword=decision.get("keyword"),
        elapsed_ms=decision.get("elapsed_ms"),
    )

    def generate():
        yield ": connected\n\n"
        yield _stream_event({
            "type": "decision",
            "label": decision["label"],
            "confidence": decision["confidence"],
            "layer": decision["layer"],
            "keyword": decision.get("keyword"),
            "elapsed_ms": decision.get("elapsed_ms"),
        })
        # Replies produced earlier in this same turn, so later agents can see
        # what earlier agents already answered (group-chat relay semantics).
        prior_replies: List[Dict[str, Any]] = []

        for member in resolved:
            persona_dict = team_orchestrator.member_persona_dict(member)
            persona_id = persona_dict.get("id")
            speaker_name = persona_dict.get("name") or "成员"

            member_context = context_messages + prior_replies
            messages, use_vision, route = build_llm_messages(
                persona_dict, member_context, attachments, base_url=str(http_request.base_url)
            )
            _inject_knowledge(db, persona_id, messages)

            member_vision = _count_vision_images(messages)
            member_input_text = _messages_plain_text(messages)

            yield _stream_event({
                "type": "agent_start",
                "persona_id": persona_id,
                "speaker_name": speaker_name,
            })

            full_content = ""
            emitted_any = False
            charge_failed = False
            try:
                stream = get_chat_completion(
                    messages, stream=True, use_vision=use_vision, raise_error=True
                )
                if not stream:
                    full_content = "抱歉，我暂时无法调用模型服务。"
                    yield _stream_event({
                        "type": "delta", "persona_id": persona_id,
                        "speaker_name": speaker_name, "content": full_content,
                    })
                else:
                    for chunk in stream:
                        piece = _chunk_content(chunk, use_vision=use_vision)
                        if piece:
                            emitted_any = True
                            full_content += piece
                            yield _stream_event({
                                "type": "delta", "persona_id": persona_id,
                                "speaker_name": speaker_name, "content": piece,
                            })

                    if not emitted_any:
                        full_content = "抱歉，我暂时无法生成内容。"
                        yield _stream_event({
                            "type": "delta", "persona_id": persona_id,
                            "speaker_name": speaker_name, "content": full_content,
                        })

                # Charge this agent's turn.
                try:
                    usage = credit_service.estimate_from_text(
                        db,
                        input_text=member_input_text,
                        output_text=full_content,
                        vision_count=member_vision,
                    )
                    credit_service.charge(
                        db,
                        current_user.id,
                        category="team_chat",
                        tokens_input=usage["tokens_input"],
                        tokens_output=usage["tokens_output"],
                        vision_count=usage["vision_count"],
                        reference_type="team",
                        reference_id=team.id,
                        note="团队群聊消耗",
                    )
                except credit_service.InsufficientCreditsError as credit_exc:
                    charge_failed = True
                    logger.warning("Insufficient credits during team turn: %s", credit_exc)
                    yield _stream_event({
                        "error": f"积分余额不足（当前 {credit_exc.balance}，预计需要 {credit_exc.required}），后续成员已停止回复。",
                        "kind": "insufficient_credits",
                        "persona_id": persona_id,
                        "speaker_name": speaker_name,
                    })
                except Exception as charge_exc:
                    logger.warning("Team charge failed for user %s: %s", current_user.id, charge_exc)

                # Decide whether this reply should carry a locally generated
                # artifact, and attach it to the SAME message (WeChat-style).
                artifacts: List[Dict[str, Any]] = []
                decision_artifact = decision.get("artifact") or {}
                artifact_type = decision_artifact.get("artifact_type") or _decide_artifact_type(content, route)
                if artifact_type and full_content.strip() and not charge_failed:
                    try:
                        artifacts.append(
                            _build_generated_artifact(artifact_type, speaker_name, full_content)
                        )
                    except Exception as art_exc:
                        logger.warning("Failed to render team artifact: %s", art_exc)
                        artifacts = []

                save_team_message(
                    db,
                    team_id=team.id,
                    sender_type="assistant",
                    speaker_name=speaker_name,
                    content=full_content,
                    user_id=None,
                    persona_id=persona_id,
                    attachments=artifacts,
                    mentioned_persona_ids=[],
                    message_type="artifact" if artifacts else "text",
                )
                # Push the artifact onto the same in-flight bubble, not as a
                # separate message.
                for art in artifacts:
                    yield _stream_event({
                        "type": "artifact",
                        "persona_id": persona_id,
                        "speaker_name": speaker_name,
                        "attachment": art,
                    })
                # Only relay a successful reply to the next agent in the same turn.
                if not charge_failed:
                    prior_replies.append({"speaker": speaker_name, "content": full_content})

                yield _stream_event({
                    "type": "agent_end", "persona_id": persona_id, "speaker_name": speaker_name,
                })

                if charge_failed:
                    break
            except LLMServiceError as exc:
                # Keep whatever partial reply was already generated; fall back to
                # the error message only if nothing streamed in yet.
                persisted = full_content.strip() or exc.message
                save_team_message(
                    db,
                    team_id=team.id,
                    sender_type="assistant",
                    speaker_name=speaker_name,
                    content=persisted,
                    user_id=None,
                    persona_id=persona_id,
                    attachments=[],
                    mentioned_persona_ids=[],
                    message_type="text",
                )
                yield _stream_event({
                    "error": exc.message, "kind": exc.kind,
                    "persona_id": persona_id, "speaker_name": speaker_name,
                })
                yield _stream_event({
                    "type": "agent_end", "persona_id": persona_id, "speaker_name": speaker_name,
                })
            except Exception as exc:
                logger.exception("Team agent stream failed: %s", exc)
                error_text = str(exc)
                persisted = full_content.strip() or error_text
                save_team_message(
                    db,
                    team_id=team.id,
                    sender_type="assistant",
                    speaker_name=speaker_name,
                    content=persisted,
                    user_id=None,
                    persona_id=persona_id,
                    attachments=[],
                    mentioned_persona_ids=[],
                    message_type="text",
                )
                yield _stream_event({
                    "error": error_text, "persona_id": persona_id, "speaker_name": speaker_name,
                })
                yield _stream_event({
                    "type": "agent_end", "persona_id": persona_id, "speaker_name": speaker_name,
                })

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers=SSE_HEADERS)


def _team_to_dict(team: Any) -> Dict[str, Any]:
    members = []
    for m in getattr(team, "members", []) or []:
        persona = getattr(m, "persona", None)
        members.append({
            "persona_id": getattr(m, "persona_id", None),
            "role": getattr(m, "role", "member"),
            "name": getattr(persona, "name", "") if persona else "",
            "title": getattr(persona, "title", None) if persona else None,
            "bio": getattr(persona, "bio", None) if persona else None,
            "avatar": getattr(persona, "avatar", None) if persona else None,
        })
    return {
        "id": team.id,
        "owner_id": getattr(team, "owner_id", None),
        "name": getattr(team, "name", ""),
        "description": getattr(team, "description", "") or "",
        "members": members,
        "created_at": getattr(team, "created_at", None),
    }


def _message_to_dict(msg: Any) -> Dict[str, Any]:
    return {
        "id": msg.id,
        "team_id": getattr(msg, "team_id", None),
        "sender_type": getattr(msg, "sender_type", ""),
        "user_id": getattr(msg, "user_id", None),
        "persona_id": getattr(msg, "persona_id", None),
        "speaker_name": getattr(msg, "speaker_name", ""),
        "content": getattr(msg, "content", ""),
        "attachments": getattr(msg, "attachments", []) or [],
        "mentioned_persona_ids": getattr(msg, "mentioned_persona_ids", []) or [],
        "message_type": getattr(msg, "message_type", "text"),
        "created_at": getattr(msg, "created_at", None),
    }


__all__ = ["router"]
