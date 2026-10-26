"""难度自适应组卷：按蓝图把题量拆到各难度档并抽样。

设计要点：
- `allocate` 是纯函数（不碰数据库），负责把总题量按比例整数化，便于单测；
- `adaptive_questions` 负责从各难度档可用题里抽样，某档库存不足时把缺口
  回补到其他仍有余量的档，保证"不静默少题"；基础池整体不够时抛 ValueError
  （由路由转成 400，文案与现有「库存不足」一致）。
"""

from __future__ import annotations

import random
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Question

# 蓝图：名称 -> 三档占比（和为 1）。占比决定"目标题量"与"回补优先级"。
BLUEPRINTS: dict[str, dict[str, float]] = {
    "intro": {"easy": 0.60, "medium": 0.30, "hard": 0.10},
    "consolidate": {"easy": 0.20, "medium": 0.55, "hard": 0.25},
    "balanced": {"easy": 0.33, "medium": 0.34, "hard": 0.33},
    "sprint": {"easy": 0.10, "medium": 0.30, "hard": 0.60},
}

BLUEPRINT_TEXT = {
    "intro": "入门",
    "consolidate": "夯实",
    "balanced": "均衡",
    "sprint": "冲刺",
}

# 标题里用的短名（易/中/难）
DIFFICULTY_SHORT = {"easy": "易", "medium": "中", "hard": "难"}

DIFFICULTIES = ["easy", "medium", "hard"]


def allocate(count: int, blueprint: str) -> dict[str, int]:
    """把 count 按蓝图拆成三档整数目标量，合计严格等于 count。

    整数化：先按比例向下取整，余数按蓝图权重从大到小逐个补（优先补占比最大的档）。
    """
    weights = BLUEPRINTS[blueprint]
    raw = {d: count * weights[d] for d in DIFFICULTIES}
    floor = {d: int(raw[d]) for d in DIFFICULTIES}
    remainder = count - sum(floor.values())
    # 权重相同（如 balanced 0.33/0.34/0.33）时用稳定顺序：中 > 难 > 易
    order = sorted(DIFFICULTIES, key=lambda d: (-weights[d], d))
    i = 0
    while remainder > 0:
        floor[order[i % len(order)]] += 1
        remainder -= 1
        i += 1
    return floor


def adaptive_questions(
    db: Session,
    user_id: int,
    count: int,
    types: list[str],
    blueprint: str,
    entry_ids: Optional[list[int]] = None,
) -> tuple[list[Question], dict[str, int]]:
    """按蓝图难度分布抽题。

    返回 (题目列表, 实际各档抽题数)。某档库存不足时回补到其他档；
    基础池总量 < count 抛 ValueError（由路由转 400）。
    """
    if blueprint not in BLUEPRINTS:
        raise ValueError(f"未知的难度蓝图：{blueprint}")

    base = db.query(Question).filter(
        Question.user_id == user_id,
        Question.status == "active",
        Question.review_status == "approved",
        Question.q_type.in_(types),
    )
    if entry_ids:
        base = base.filter(Question.entry_id.in_(entry_ids))

    # 各档可用题 id（排除已选，避免回补时重复抽）
    available: dict[str, list[int]] = {}
    for d in DIFFICULTIES:
        available[d] = [
            row[0]
            for row in base.filter(Question.difficulty == d)
            .with_entities(Question.id)
            .all()
        ]

    targets = allocate(count, blueprint)
    chosen_ids: set[int] = set()
    actual: dict[str, int] = {d: 0 for d in DIFFICULTIES}

    def take_from(d: str, n: int) -> int:
        pool = [qid for qid in available[d] if qid not in chosen_ids]
        random.shuffle(pool)
        take = min(n, len(pool))
        for qid in pool[:take]:
            chosen_ids.add(qid)
        actual[d] += take
        return take

    # 第一轮：按目标量抽
    for d in DIFFICULTIES:
        take_from(d, targets[d])

    # 第二轮：某档库存不足产生的缺口，按蓝图权重从大到小回补到仍有余量的档
    deficit = count - sum(actual.values())
    if deficit > 0:
        order = sorted(DIFFICULTIES, key=lambda d: (-BLUEPRINTS[blueprint][d], d))
        i = 0
        while deficit > 0 and order:
            d = order[i % len(order)]
            got = take_from(d, 1)
            if got == 0:
                order = [x for x in order if x != d]  # 该档已无余量，移出轮转
                if not order:
                    break
                continue
            deficit -= 1
            i += 1

    if sum(actual.values()) < count:
        avail_total = sum(len(v) for v in available.values())
        raise ValueError(
            f"该筛选下可组题目仅 {sum(actual.values())} 道（可用候选 {avail_total} 道），"
            f"不足 {count} 道，请减少数量或放宽筛选条件"
        )

    questions = db.query(Question).filter(Question.id.in_(chosen_ids)).all()
    random.shuffle(questions)
    return questions, actual
