"""运行时配置：支持 .env 文件、环境变量与数据库覆盖（Web 配置页）。"""

from dataclasses import dataclass
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行时配置：支持 .env 文件与环境变量覆盖。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "面试题录入训练系统"
    api_prefix: str = "/api"
    # development：占位密钥只告警；production：占位密钥直接拒绝启动
    app_env: str = "development"

    # 关系数据库（默认 SQLite 零部署；换 PostgreSQL 改这一项即可）
    database_url: str = "sqlite:///./data/interview_trainer.db"

    # 向量数据库持久化目录
    chroma_dir: str = "./data/chroma"

    # JWT
    jwt_secret: str = "change-me-in-production-use-a-long-random-secret-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # LLM（OpenAI 兼容协议），两项都为空 => 规则引擎演示模式
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 120

    # Embedding（可独立于 LLM 配置；为空 => 内置确定性向量）
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"

    # 知识库处理参数
    chunk_target_size: int = 400
    chunk_max_size: int = 600

    # 出题参数
    question_dedup_threshold: float = 0.95
    embedding_dim: int = 384

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key)

    @property
    def embedding_enabled(self) -> bool:
        return bool(self.embedding_base_url and self.embedding_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------- 启动安全校验
# 代码默认值 + .env.example 里的示例值：两者都是「没配」，必须一起拦
PLACEHOLDER_JWT_SECRETS = frozenset(
    {
        "change-me-in-production-use-a-long-random-secret-string",
        "please-change-me-in-production",
    }
)
JWT_SECRET_MIN_LENGTH = 32


def is_placeholder_jwt_secret(secret: str) -> bool:
    """占位值或长度不足的密钥一律视为未配置。"""
    value = (secret or "").strip()
    return value in PLACEHOLDER_JWT_SECRETS or len(value) < JWT_SECRET_MIN_LENGTH


def assert_jwt_secret(settings: Settings) -> None:
    """生产环境用占位密钥直接拒绝启动，开发环境只告警。

    占位密钥是公开的：任何人都能伪造 Token 冒充任意用户，因此生产环境
    必须 fail-fast，而不是依赖部署者记得改。
    """
    if not is_placeholder_jwt_secret(settings.jwt_secret):
        return

    message = (
        f"JWT_SECRET 仍为占位值或长度不足 {JWT_SECRET_MIN_LENGTH} 位，"
        "签发的 Token 可被伪造"
    )
    if settings.app_env.strip().lower() in {"production", "prod"}:
        raise RuntimeError(
            f"{message}；APP_ENV=production 拒绝启动。"
            "请用 `python -c \"import secrets;print(secrets.token_urlsafe(48))\"` 生成后写入 .env"
        )
    print(f"[warn] {message}（开发环境放行；生产请设 APP_ENV=production）")


# ---------------------------------------------------------------- 运行时生效配置
@dataclass
class EffectiveSettings:
    """合并 .env 与数据库覆盖项后的运行时配置视图（只读快照）。"""

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 120
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dim: int = 384
    chunk_target_size: int = 400
    chunk_max_size: int = 600
    question_dedup_threshold: float = 0.95

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key)

    @property
    def embedding_enabled(self) -> bool:
        return bool(self.embedding_base_url and self.embedding_api_key)


def effective_settings() -> EffectiveSettings:
    """DB 覆盖项优先于 .env；未覆盖的字段回退 .env 值。"""
    from .services.settings_store import load_overrides

    base = get_settings()
    overrides = load_overrides()

    def pick(attr: str) -> str:
        value = overrides.get(attr)
        if value is None or value == "":
            return getattr(base, attr)
        return value

    def pick_int(attr: str) -> int:
        raw = overrides.get(attr)
        if raw is None or raw == "":
            return getattr(base, attr)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return getattr(base, attr)

    return EffectiveSettings(
        llm_base_url=pick("llm_base_url"),
        llm_api_key=pick("llm_api_key"),
        llm_model=pick("llm_model"),
        llm_timeout_seconds=pick_int("llm_timeout_seconds"),
        embedding_base_url=pick("embedding_base_url"),
        embedding_api_key=pick("embedding_api_key"),
        embedding_model=pick("embedding_model"),
        embedding_dim=base.embedding_dim,
        chunk_target_size=base.chunk_target_size,
        chunk_max_size=base.chunk_max_size,
        question_dedup_threshold=base.question_dedup_threshold,
    )
