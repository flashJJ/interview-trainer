"""系统配置的数据库存储。

优先级：system_configs 表（Web 配置页保存）> .env 文件 > 代码默认值。
保存后即时生效，无需重启服务。
"""

from datetime import datetime

# 允许通过 Web 配置页覆盖的配置项
OVERRIDE_KEYS = (
    "llm_base_url",
    "llm_api_key",
    "llm_model",
    "llm_timeout_seconds",
    "embedding_base_url",
    "embedding_api_key",
    "embedding_model",
)


def load_overrides() -> dict:
    """读取全部配置覆盖项；表不存在或查询失败时返回空 dict（不影响主流程）。"""
    from ..database import SessionLocal
    from ..models import SystemConfig

    db = SessionLocal()
    try:
        rows = db.query(SystemConfig).all()
        return {row.key: row.value for row in rows}
    except Exception:  # noqa: BLE001 - 配置读取失败时静默回退 .env
        return {}
    finally:
        db.close()


def save_overrides(data: dict) -> None:
    """保存配置覆盖项（仅接受 OVERRIDE_KEYS 中的键）。"""
    from ..database import SessionLocal
    from ..models import SystemConfig

    db = SessionLocal()
    try:
        for key, value in data.items():
            if key not in OVERRIDE_KEYS:
                continue
            row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if row is None:
                db.add(SystemConfig(key=key, value=str(value)))
            else:
                row.value = str(value)
                row.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def clear_overrides() -> None:
    """清除全部覆盖项，回退到 .env 配置。"""
    from ..database import SessionLocal
    from ..models import SystemConfig

    db = SessionLocal()
    try:
        db.query(SystemConfig).delete()
        db.commit()
    finally:
        db.close()


def mask_secret(value: str) -> str:
    """API Key 脱敏展示：sk-ab****wxyz。"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"
