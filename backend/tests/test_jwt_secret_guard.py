"""JWT 占位密钥的启动守卫：生产必须 fail-fast，开发只告警。

背景：默认密钥是公开的（写在代码与 .env.example 里），任何人都能用它伪造
Token 冒充任意用户。容器化部署后「忘了改」的成本被放大，所以在 lifespan
里做一次显式校验，并用单测把两个占位串都钉住。
"""

import pytest

from app.config import (
    JWT_SECRET_MIN_LENGTH,
    assert_jwt_secret,
    is_placeholder_jwt_secret,
    Settings,
)


class TestIsPlaceholder:
    def test_code_default_is_placeholder(self):
        # 与 Settings.jwt_secret 的默认值保持一致
        assert is_placeholder_jwt_secret(Settings().jwt_secret)

    def test_env_example_value_is_placeholder(self):
        assert is_placeholder_jwt_secret("please-change-me-in-production")

    def test_too_short_is_placeholder(self):
        assert is_placeholder_jwt_secret("short-secret")

    def test_empty_is_placeholder(self):
        assert is_placeholder_jwt_secret("")
        assert is_placeholder_jwt_secret("   ")

    def test_long_random_is_accepted(self):
        assert not is_placeholder_jwt_secret("x" * JWT_SECRET_MIN_LENGTH)
        assert not is_placeholder_jwt_secret("Qm9zdG9uLXNlY3JldC1ub3QtZ3Vlc3NhYmxlLTEyMzQ1Ng")


class TestAssertJwtSecret:
    def test_production_refuses_to_start(self):
        settings = Settings(app_env="production", jwt_secret="please-change-me-in-production")
        with pytest.raises(RuntimeError, match="拒绝启动"):
            assert_jwt_secret(settings)

    @pytest.mark.parametrize("env", ["production", "PROD", " Production "])
    def test_production_env_variants_are_strict(self, env):
        settings = Settings(app_env=env, jwt_secret="short")
        with pytest.raises(RuntimeError):
            assert_jwt_secret(settings)

    def test_development_only_warns(self, capsys):
        settings = Settings(app_env="development", jwt_secret="please-change-me-in-production")
        assert_jwt_secret(settings)  # 不抛异常
        assert "[warn]" in capsys.readouterr().out

    def test_production_with_strong_secret_passes(self):
        settings = Settings(app_env="production", jwt_secret="y" * 48)
        assert_jwt_secret(settings)  # 不抛异常
