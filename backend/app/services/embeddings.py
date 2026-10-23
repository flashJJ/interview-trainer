"""向量化服务：优先调用 OpenAI 兼容 Embedding API，不可用时使用内置确定性向量。

内置向量为中文 n-gram TF-IDF 哈希（见 text_utils），对中文技术文本的检索与
相似度判断有可用的基线效果，保证系统零配置可跑。

配置实时生效：每次 embed 时读取当前配置（.env + DB 覆盖）；
某个配置指纹调用失败后记入黑名单，配置变化（指纹不同）后自动重新尝试。
"""

import httpx

from . import text_utils


class EmbeddingService:
    def __init__(self, settings=None):
        self._fixed_settings = settings
        self._failed_fp = None  # 调用失败的配置指纹
        self._warned = False

    # ------------------------------------------------------------ 配置读取
    @property
    def _cfg(self):
        if self._fixed_settings is not None:
            return self._fixed_settings
        from ..config import effective_settings

        return effective_settings()

    @property
    def settings(self):
        """兼容旧访问方式：返回当前生效配置。"""
        return self._cfg

    @staticmethod
    def _fp(cfg) -> tuple:
        return (cfg.embedding_base_url, cfg.embedding_api_key, cfg.embedding_model)

    @property
    def mode(self) -> str:
        cfg = self._cfg
        if not cfg.embedding_enabled or self._failed_fp == self._fp(cfg):
            return "local"
        return "api"

    # ------------------------------------------------------------ 向量化
    def embed(self, text: str) -> list[float]:
        cfg = self._cfg
        if cfg.embedding_enabled and self._failed_fp != self._fp(cfg):
            try:
                return self._embed_api(cfg, [text])[0]
            except Exception as exc:  # noqa: BLE001 - 任何 API 失败都降级
                self._fallback(exc, cfg)
        return text_utils.embed_text(text, cfg.embedding_dim)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        cfg = self._cfg
        if cfg.embedding_enabled and self._failed_fp != self._fp(cfg):
            try:
                return self._embed_api(cfg, texts)
            except Exception as exc:  # noqa: BLE001
                self._fallback(exc, cfg)
        return [text_utils.embed_text(t, cfg.embedding_dim) for t in texts]

    def _embed_api(self, cfg, texts: list[str]) -> list[list[float]]:
        base = cfg.embedding_base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {cfg.embedding_api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{base}/embeddings",
                headers=headers,
                json={"model": cfg.embedding_model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        items = sorted(data["data"], key=lambda d: d.get("index", 0))
        return [item["embedding"] for item in items]

    def _fallback(self, exc: Exception, cfg) -> None:
        # 记录失败的配置指纹：配置不变则不再重试，配置变化后自动重新尝试
        self._failed_fp = self._fp(cfg)
        if not self._warned:
            self._warned = True
            print(f"[embeddings] API 调用失败，已降级为内置确定性向量：{exc}")
