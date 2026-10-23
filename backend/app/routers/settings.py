"""系统配置路由：LLM/Embedding 配置的读取、保存、测试连接与重置，以及修改密码。

配置保存后写入 system_configs 表（优先级高于 .env），下次请求即时生效，无需重启。
"""

import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import effective_settings, get_settings
from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import (
    ChangePasswordIn,
    SystemConfigIn,
    SystemConfigOut,
    TestConnectionIn,
    TestConnectionOut,
)
from ..security import hash_password, verify_password
from ..services.llm_client import LLMClient
from ..services.runtime import get_embeddings
from ..services.settings_store import (
    clear_overrides,
    load_overrides,
    mask_secret,
    save_overrides,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _config_out() -> SystemConfigOut:
    base = get_settings()
    overrides = load_overrides()
    effective = effective_settings()

    def current(attr: str) -> str:
        value = overrides.get(attr)
        if value is None or value == "":
            return str(getattr(base, attr))
        return value

    return SystemConfigOut(
        llm_base_url=current("llm_base_url"),
        llm_api_key_masked=mask_secret(current("llm_api_key")),
        llm_api_key_set=bool(current("llm_api_key")),
        llm_model=current("llm_model"),
        llm_timeout_seconds=int(current("llm_timeout_seconds") or 120),
        embedding_base_url=current("embedding_base_url"),
        embedding_api_key_masked=mask_secret(current("embedding_api_key")),
        embedding_api_key_set=bool(current("embedding_api_key")),
        embedding_model=current("embedding_model"),
        llm_enabled=effective.llm_enabled,
        embedding_mode=get_embeddings().mode,
    )


@router.get("", response_model=SystemConfigOut)
def get_config(current_user: User = Depends(get_current_user)):
    return _config_out()


@router.put("", response_model=SystemConfigOut)
def save_config(
    payload: SystemConfigIn,
    current_user: User = Depends(get_current_user),
):
    data = {}
    for key, value in payload.model_dump().items():
        if value is None:
            continue  # 未修改
        # 防止把脱敏值（含 ****）写回存储
        if isinstance(value, str) and "****" in value:
            continue
        data[key] = value
    save_overrides(data)
    return _config_out()


@router.post("/reset", response_model=SystemConfigOut)
def reset_config(current_user: User = Depends(get_current_user)):
    """清除全部覆盖项，回退 .env 配置。"""
    clear_overrides()
    return _config_out()


@router.post("/test", response_model=TestConnectionOut)
def test_connection(
    payload: TestConnectionIn,
    current_user: User = Depends(get_current_user),
):
    """用给定配置（未保存也可）发起一次最小真实请求，验证连通性。"""
    cfg = effective_settings()
    started = time.time()

    if payload.target == "embedding":
        base = payload.embedding_base_url or cfg.embedding_base_url
        key = payload.embedding_api_key or cfg.embedding_api_key
        model = payload.embedding_model or cfg.embedding_model
        if not (base and key):
            return TestConnectionOut(ok=False, error="Embedding 未完整配置（Base URL 与 API Key 必填）")
        from ..config import EffectiveSettings
        from ..services.embeddings import EmbeddingService

        probe = EmbeddingService(
            EffectiveSettings(
                embedding_base_url=base,
                embedding_api_key=key,
                embedding_model=model,
            )
        )
        try:
            vector = probe.embed("连通性测试")
        except Exception as exc:  # noqa: BLE001
            return TestConnectionOut(ok=False, error=str(exc)[:300])
        if not vector:
            return TestConnectionOut(ok=False, error="接口返回了空向量")
        return TestConnectionOut(
            ok=True,
            latency_ms=int((time.time() - started) * 1000),
            detail=f"连接成功，向量维度 {len(vector)}（模型：{model}）",
        )

    # 默认测试 LLM
    base = payload.llm_base_url or cfg.llm_base_url
    key = payload.llm_api_key or cfg.llm_api_key
    model = payload.llm_model or cfg.llm_model
    if not (base and key):
        return TestConnectionOut(ok=False, error="LLM 未完整配置（Base URL 与 API Key 必填）")
    from ..config import EffectiveSettings

    probe = LLMClient(
        EffectiveSettings(
            llm_base_url=base,
            llm_api_key=key,
            llm_model=model,
            llm_timeout_seconds=30,
        )
    )
    try:
        reply = probe.chat(
            [{"role": "user", "content": "请只回复两个字：正常"}],
            max_tokens=16,
        )
    except Exception as exc:  # noqa: BLE001
        return TestConnectionOut(ok=False, error=str(exc)[:300])
    return TestConnectionOut(
        ok=True,
        latency_ms=int((time.time() - started) * 1000),
        detail=f"连接成功，模型回复：{(reply or '').strip()[:50]}",
    )


@router.post("/password")
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "原密码错误")
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True, "message": "密码已修改，请使用新密码重新登录"}
