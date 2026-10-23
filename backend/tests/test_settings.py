"""系统配置模块单测：DB 覆盖、优先级合并、脱敏。"""

from app.config import EffectiveSettings, effective_settings, get_settings
from app.services.settings_store import (
    clear_overrides,
    load_overrides,
    mask_secret,
    save_overrides,
)


class TestMaskSecret:
    def test_empty(self):
        assert mask_secret("") == ""

    def test_short(self):
        assert mask_secret("abc") == "****"

    def test_normal(self):
        assert mask_secret("sk-abcdefgh1234") == "sk-a****1234"


class TestOverrides:
    def test_save_load_clear_roundtrip(self):
        save_overrides({"llm_base_url": "https://api.example.com", "llm_api_key": "sk-test"})
        data = load_overrides()
        assert data["llm_base_url"] == "https://api.example.com"
        assert data["llm_api_key"] == "sk-test"
        clear_overrides()
        assert "llm_base_url" not in load_overrides()

    def test_save_updates_existing(self):
        save_overrides({"llm_model": "model-a"})
        save_overrides({"llm_model": "model-b"})
        assert load_overrides()["llm_model"] == "model-b"
        clear_overrides()

    def test_save_ignores_unknown_keys(self):
        save_overrides({"not_a_real_key": "x"})
        assert "not_a_real_key" not in load_overrides()

    def test_load_overrides_never_raises(self):
        # 空库/异常场景应返回空 dict 而不是抛错
        assert isinstance(load_overrides(), dict)


class TestEffectiveSettings:
    def test_no_override_uses_env(self):
        clear_overrides()
        cfg = effective_settings()
        base = get_settings()
        assert cfg.llm_model == base.llm_model
        assert cfg.embedding_dim == base.embedding_dim
        assert cfg.llm_enabled is False  # 测试环境无 Key

    def test_override_takes_priority(self):
        clear_overrides()
        save_overrides({"llm_base_url": "https://api.test.com", "llm_api_key": "sk-xyz"})
        cfg = effective_settings()
        assert cfg.llm_base_url == "https://api.test.com"
        assert cfg.llm_api_key == "sk-xyz"
        assert cfg.llm_enabled is True
        clear_overrides()
        # 清除后恢复 .env 行为
        assert effective_settings().llm_enabled is False

    def test_empty_override_falls_back(self):
        clear_overrides()
        base = get_settings()
        save_overrides({"llm_model": ""})  # 空值视为未覆盖
        assert effective_settings().llm_model == base.llm_model
        clear_overrides()

    def test_invalid_int_override_falls_back(self):
        clear_overrides()
        base = get_settings()
        save_overrides({"llm_timeout_seconds": "not-a-number"})
        assert effective_settings().llm_timeout_seconds == base.llm_timeout_seconds
        clear_overrides()

    def test_embedding_override(self):
        clear_overrides()
        save_overrides(
            {
                "embedding_base_url": "https://emb.example.com/v1",
                "embedding_api_key": "sk-emb",
                "embedding_model": "bge-m3",
            }
        )
        cfg = effective_settings()
        assert cfg.embedding_enabled is True
        assert cfg.embedding_model == "bge-m3"
        clear_overrides()

    def test_fixed_settings_object(self):
        # LLMClient/EmbeddingService 可接受固定配置（测试连接场景）
        fixed = EffectiveSettings(llm_base_url="https://x.com", llm_api_key="k", llm_model="m")
        assert fixed.llm_enabled is True
        assert fixed.embedding_enabled is False
