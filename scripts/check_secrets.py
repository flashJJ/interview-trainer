#!/usr/bin/env python3
"""推送前脱敏扫描：在开源仓库里拦住真实密钥与本机绝对路径。

只扫 git **跟踪**的文件（未跟踪的 .env / *.db 本来就不该进仓库，
若它们被 add 了也会出现在这里）。二进制与图片直接跳过。

用法：
    python scripts/check_secrets.py            # 全量扫描（推送前跑）
    python scripts/check_secrets.py --staged   # 只扫暂存区（pre-commit 场景）

退出码：0 干净；1 发现疑似敏感信息（CI 会因此失败）

注意：命中「示例 / 占位 / xxx」等提示词的行会被放行，这是为了不误伤文档里的
反例。代价是“真实密钥恰好和示例词写在同一行”会被漏掉——请不要那么写。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip",
    ".woff", ".woff2", ".ttf", ".eot", ".db", ".pyc", ".xlsx", ".docx",
}

# 行内出现这些提示词 => 视为文档示例，放行
ALLOW_HINTS = (
    "示例", "占位", "placeholder", "your-", "xxx", "xxxx",
    "change-me", "please-change", "<your", "****", "…",
)

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI/DeepSeek 风格 Key", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")),
    ("火山方舟套餐 Key", re.compile(r"\bark-[A-Za-z0-9-]{16,}\b")),
    ("GitHub PAT (ghp_)", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("GitHub OAuth (gho_)", re.compile(r"\bgho_[A-Za-z0-9]{20,}\b")),
    ("GitHub 细粒度 Token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("私钥块", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Windows 本机绝对路径", re.compile(r"(?i)\b[a-z]:[\\/](?:users|code|traework|workbuddy)[\\/]")),
    ("macOS 家目录路径", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("内网/本机服务地址", re.compile(r"https?://(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.")),
]

# 允许存在的配置样例文件
ALLOW_FILENAMES = {".env.example", ".env.sample", ".env.template"}


def tracked_files(staged: bool) -> list[str]:
    cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged else ["git", "ls-files"]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def is_allowed_line(line: str) -> bool:
    lower = line.lower()
    return any(hint.lower() in lower for hint in ALLOW_HINTS)


def scan(staged: bool) -> int:
    findings: list[str] = []
    name_hits: list[str] = []

    for rel in tracked_files(staged):
        path = ROOT / rel
        name = path.name
        if name.startswith(".env") and name not in ALLOW_FILENAMES:
            name_hits.append(rel)
        if path.suffix.lower() in SKIP_EXT or not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not line.strip() or is_allowed_line(line):
                continue
            for label, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append(f"{rel}:{lineno}  [{label}]  {line.strip()[:120]}")

    print(f"[scope] 扫描 {len(tracked_files(staged))} 个跟踪文件"
          f"{'（暂存区）' if staged else ''}")

    if name_hits:
        print("\n[!!] 不该入库的配置文件：")
        for item in name_hits:
            print(f"  - {item}")
    if findings:
        print(f"\n[!!] 命中 {len(findings)} 处疑似敏感信息：")
        for item in findings[:40]:
            print(f"  - {item}")
        if len(findings) > 40:
            print(f"  … 另有 {len(findings) - 40} 处")
    if name_hits or findings:
        print("\n[FAIL] 请替换为占位值（如 your-key-here）或从版本库移除后重试。")
        return 1

    print("[OK] 未发现真实密钥与本机绝对路径")
    return 0


if __name__ == "__main__":
    sys.exit(scan(staged="--staged" in sys.argv))
