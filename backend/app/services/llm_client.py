"""OpenAI 兼容协议 LLM 客户端，带 JSON 提取与修复能力。"""

import json
import re

import httpx

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str):
    """从模型输出中提取第一个合法 JSON 值（容忍 markdown 围栏与前后废话）。"""
    if not text:
        raise ValueError("空输出")
    cleaned = _FENCE_RE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass
    decoder = json.JSONDecoder()
    for i, ch in enumerate(cleaned):
        if ch in "[{":
            try:
                obj, _ = decoder.raw_decode(cleaned[i:])
                return obj
            except json.JSONDecodeError:
                continue
    raise ValueError(f"无法从模型输出解析 JSON：{cleaned[:120]}...")


class LLMClient:
    """OpenAI 兼容协议客户端。

    settings 为 None 时每次调用实时读取生效配置（.env + DB 覆盖），
    保证 Web 配置页保存后无需重启即可生效；传入 settings 则固定使用（测试连接用）。
    """

    def __init__(self, settings=None):
        self._fixed_settings = settings

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

    @property
    def enabled(self) -> bool:
        return self._cfg.llm_enabled

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 1500) -> str:
        cfg = self._cfg
        if not cfg.llm_enabled:
            raise RuntimeError("LLM 未配置（请在系统配置页或 .env 中填写 Base URL 与 API Key）")
        url = cfg.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg.llm_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": cfg.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=cfg.llm_timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]

    def chat_json(self, messages: list[dict], temperature: float = 0.3):
        """调用并解析 JSON；解析失败时带上下文请求模型自我修复（最多 2 次）。"""
        messages = list(messages)
        raw = ""
        for attempt in range(3):
            try:
                raw = self.chat(messages, temperature=temperature)
                return extract_json(raw)
            except Exception:  # noqa: BLE001 - 网络/解析/校验失败都走修复重试
                if attempt == 2:
                    raise
                messages.append({"role": "assistant", "content": raw[:500]})
                messages.append(
                    {
                        "role": "user",
                        "content": "你的上次输出无法解析为合法 JSON。请只输出一个合法 JSON 对象，"
                        "字段必须齐全，不要输出任何解释文字或代码块围栏。",
                    }
                )
        raise RuntimeError("unreachable")
