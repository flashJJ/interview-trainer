"""全链路 API 冒烟测试：登录 -> 录入 -> 出题 -> 组卷 -> 考试 -> 评分 -> 分析。"""

import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api"
passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=60, trust_env=False) as client:
        # ---------- 1. 认证 ----------
        print("[1] 认证")
        # 每次运行使用独立用户：出题去重按用户隔离，保证测试可重复执行
        run_tag = f"smoke_{int(time.time())}"
        resp = client.post(
            "/auth/register",
            json={"username": run_tag, "password": "smoke123", "email": "s@x.com"},
        )
        check("注册新用户", resp.status_code == 200, resp.text)

        resp = client.post("/auth/login", json={"username": run_tag, "password": "smoke123"})
        check("登录", resp.status_code == 200, resp.text)
        token = resp.json().get("access_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/auth/me", headers=headers)
        check("获取当前用户", resp.status_code == 200 and resp.json()["username"] == run_tag, resp.text[:100])

        resp = client.get("/auth/me")
        check("无 token 访问被拒绝(401)", resp.status_code == 401)

        # ---------- 2. 知识库 ----------
        print("[2] 知识库录入与处理")
        content = (
            "HTTP 缓存机制通过响应头控制浏览器与代理服务器的缓存行为。"
            "Cache-Control 是最重要的缓存指令，max-age 指定资源在缓存中的新鲜期秒数，"
            "no-cache 表示每次使用前必须向服务器验证，no-store 表示完全不缓存。\n\n"
            "强缓存与协商缓存是两类核心策略：强缓存命中时直接使用本地副本，不发送请求；"
            "协商缓存则携带 Last-Modified 或 ETag 询问服务器资源是否变化，返回 304 表示可继续使用缓存。\n\n"
            "ETag 是资源内容的唯一标识，比 Last-Modified 的秒级时间戳更精确，"
            "能识别一秒内发生的内容变化，是生产环境优先采用的验证方式。"
        )
        resp = client.post(
            "/knowledge/entries",
            json={"title": f"HTTP 缓存机制 {run_tag}", "content": content},
            headers=headers,
        )
        check("文本录入知识库", resp.status_code == 200, resp.text)
        entry = resp.json()
        entry_id = entry["id"]
        check("自动处理完成(status=ready)", entry["status"] == "ready", entry["status"])
        check("自动分块(chunk_count>0)", entry["chunk_count"] > 0)
        check("关键词提取", entry["chunk_count"] >= 1)

        resp = client.get(f"/knowledge/entries/{entry_id}", headers=headers)
        detail = resp.json()
        check("条目详情含 chunks", len(detail["chunks"]) > 0 and detail["chunks"][0]["keywords"])

        resp = client.get("/knowledge/entries", headers=headers)
        check("知识库列表", resp.status_code == 200 and resp.json()["total"] >= 1)

        resp = client.post("/knowledge/search", json={"query": "缓存验证方式", "top_k": 3}, headers=headers)
        check("语义检索", resp.status_code == 200 and len(resp.json()["results"]) > 0, resp.text)

        resp = client.get("/knowledge/stats/overview", headers=headers)
        check("知识库统计", resp.json()["entry_count"] >= 1)

        # ---------- 2.5 多格式导入 ----------
        print("[2.5] 多格式导入")
        resp = client.post(
            "/knowledge/entries/upload",
            files={"file": ("evil.exe", b"MZ binary", "application/octet-stream")},
            headers=headers,
        )
        check("不支持的文件类型被拒绝", resp.status_code == 400 and "支持" in resp.json()["detail"])

        resp = client.post("/knowledge/entries/url", json={"url": "ftp://invalid"}, headers=headers)
        check("非法 URL 拒绝", resp.status_code == 400 and "http" in resp.json()["detail"])

        resp = client.post(
            "/knowledge/entries/url", json={"url": "http://127.0.0.1:9/none"}, headers=headers
        )
        check("不可达 URL 返回友好错误", resp.status_code == 400 and resp.json()["detail"])

        # ---------- 3. AI 出题 ----------
        print("[3] AI 出题")
        resp = client.post(
            "/questions/generate",
            json={"entry_id": entry_id, "types": ["choice", "fill", "judge"], "count_per_type": 2},
            headers=headers,
        )
        check("触发出题", resp.status_code == 200, resp.text)
        gen = resp.json()
        check("三类题全部生成", {q["q_type"] for q in gen["created"]} == {"choice", "fill", "judge"})
        check("题目带标准答案与解析", all(q["answer"] and q["explanation"] for q in gen["created"]))
        check("生成模式标记", gen["mode"] in ("rule", "llm"))
        choice_q = next(q for q in gen["created"] if q["q_type"] == "choice")
        check("选择题 4 个选项", len(choice_q["options"]) == 4)

        # 请求数量超过素材可支撑的不重复题目数时，多余部分应被去重跳过
        resp = client.post(
            "/questions/generate",
            json={"entry_id": entry_id, "types": ["choice"], "count_per_type": 10},
            headers=headers,
        )
        again = resp.json()
        check(
            "重复出题被去重(skipped>0)",
            again["skipped_count"] > 0 or again["created_count"] == 0,
            f"skipped={again['skipped_count']} created={again['created_count']}",
        )

        resp = client.get("/questions?q_type=choice&size=5", headers=headers)
        check("题库筛选(按题型)", resp.status_code == 200 and all(q["q_type"] == "choice" for q in resp.json()["items"]))

        resp = client.get("/questions/stats/overview", headers=headers)
        check("题库统计", resp.json()["total"] > 0)

        # ---------- 3.5 出题审核流 ----------
        print("[3.5] 出题审核流")
        # v1.2 起新生成的题默认进入待审核；先批量通过首批题（模拟人工审核），供后续组卷使用
        all_created_ids = [q["id"] for q in gen["created"]] + [q["id"] for q in again["created"]]
        resp = client.post(
            "/questions/review/batch",
            json={"question_ids": all_created_ids, "action": "approve"},
            headers=headers,
        )
        check("批量通过首批题目", resp.status_code == 200 and resp.json()["updated"] == len(all_created_ids), resp.text[:100])

        resp = client.post(
            "/questions/generate",
            json={"entry_id": entry_id, "types": ["judge"], "count_per_type": 2},
            headers=headers,
        )
        gen2 = resp.json()
        check(
            "新生成的题进入待审核",
            all(q["review_status"] == "pending" for q in gen2["created"]),
            resp.text[:100],
        )
        pending_ids = [q["id"] for q in gen2["created"]]

        resp = client.get("/questions?review_status=pending&size=10", headers=headers)
        check("待审核列表可见", resp.status_code == 200 and len(resp.json()["items"]) > 0)

        if pending_ids:
            qid = pending_ids[0]
            resp = client.put(
                f"/questions/{qid}",
                json={"explanation": "冒烟测试编辑后的解析"},
                headers=headers,
            )
            check(
                "编辑题目",
                resp.status_code == 200 and resp.json()["explanation"] == "冒烟测试编辑后的解析",
                resp.text[:100],
            )
            resp = client.post(f"/questions/{qid}/review", json={"action": "approve"}, headers=headers)
            check("单题审核通过", resp.json()["review_status"] == "approved")

        if len(pending_ids) > 1:
            resp = client.post(
                "/questions/review/batch",
                json={"question_ids": [pending_ids[1]], "action": "reject"},
                headers=headers,
            )
            check("批量审核拒绝", resp.status_code == 200 and resp.json()["updated"] == 1, resp.text[:100])

        # ---------- 4. 组卷 ----------
        print("[4] 随机组卷")
        resp = client.post(
            "/exams/generate",
            json={"title": "冒烟测试考卷", "count": 6, "types": ["choice", "fill", "judge"]},
            headers=headers,
        )
        check("随机组卷", resp.status_code == 200, resp.text)
        paper = resp.json()
        paper_id = paper["id"]
        check("题目数量正确", paper["question_count"] == 6)

        # 库存不足：限定到本次冒烟新建的资料（题目数远小于 100），应明确报错而不是静默截断
        resp = client.post(
            "/exams/generate",
            json={"count": 100, "types": ["choice", "fill", "judge"], "entry_ids": [entry_id]},
            headers=headers,
        )
        check("库存不足时明确报错", resp.status_code == 400 and "仅" in resp.json()["detail"], resp.text[:120])

        resp = client.get("/exams", headers=headers)
        check("考卷列表", resp.json()["total"] >= 1)

        resp = client.get(f"/exams/{paper_id}", headers=headers)
        paper_detail = resp.json()
        check("考卷题目不含答案", all("answer" not in q for q in paper_detail["questions"]))

        # ---------- 5. 考试与评分 ----------
        print("[5] 在线考试与 AI 评分")
        resp = client.post(f"/exams/{paper_id}/start", headers=headers)
        check("开始考试", resp.status_code == 200, resp.text)
        session = resp.json()
        session_id = session["session"]["id"]
        questions = session["questions"]

        resp = client.post(f"/exams/{paper_id}/start", headers=headers)
        check("重复开始返回同一会话(续考)", resp.json()["session"]["id"] == session_id)

        # 草稿保存与恢复
        draft = [{"question_id": questions[0]["id"], "answer": "临时草稿答案"}]
        resp = client.post(
            f"/exams/sessions/{session_id}/save", json={"answers": draft}, headers=headers
        )
        check("保存作答草稿", resp.status_code == 200 and resp.json()["saved"] == 1, resp.text[:100])
        resp = client.post(f"/exams/{paper_id}/start", headers=headers)
        resumed = resp.json()["answers"]
        check(
            "续考恢复草稿答案",
            any(
                a["question_id"] == questions[0]["id"] and a["user_answer"] == "临时草稿答案"
                for a in resumed
            ),
            str(resumed),
        )

        # 构造答案：对一半
        answers = []
        correct_flags = []
        for i, q in enumerate(questions):
            # 从题库查正确答案来构造"对/错"答卷
            qd = client.get(f"/questions/{q['id']}", headers=headers).json()
            if i % 2 == 0:
                answers.append({"question_id": q["id"], "answer": qd["answer"]})
                correct_flags.append(True)
            else:
                if q["q_type"] == "choice":
                    wrong = next(l for l in "ABCD" if l != qd["answer"])
                    answers.append({"question_id": q["id"], "answer": wrong})
                elif q["q_type"] == "judge":
                    answers.append({"question_id": q["id"], "answer": "错误" if qd["answer"] == "正确" else "正确"})
                else:
                    answers.append({"question_id": q["id"], "answer": "无关答案"})
                correct_flags.append(False)

        resp = client.post(
            f"/exams/sessions/{session_id}/submit", json={"answers": answers}, headers=headers
        )
        check("提交并评分", resp.status_code == 200, resp.text)
        result = resp.json()
        expected_correct = sum(1 for f in correct_flags if f)
        check(f"评分正确数符合预期({expected_correct})", result["correct_count"] == expected_correct, str(result["correct_count"]))
        check("总分/满分/得分率齐全", result["max_score"] == 60.0 and 0 < result["score_rate"] < 1)
        check("逐题反馈与解析", all(r["feedback"] and r["explanation"] for r in result["results"]))

        resp = client.post(
            f"/exams/sessions/{session_id}/submit", json={"answers": answers}, headers=headers
        )
        check("重复提交被拒绝", resp.status_code == 400)

        resp = client.get(f"/exams/sessions/{session_id}", headers=headers)
        check("成绩详情查询", resp.status_code == 200 and resp.json()["total_score"] == result["total_score"])

        resp = client.get("/exams/sessions", headers=headers)
        check("历史考试列表", resp.json()["total"] >= 1)

        # ---------- 5.5 错题本（SM-2） ----------
        print("[5.5] 错题本")
        resp = client.get("/wrong-questions/stats", headers=headers)
        stats = resp.json()
        check("错题本统计", resp.status_code == 200 and stats["total"] > 0, resp.text[:100])
        check("统计含到期分布", all(k in stats for k in ("due_today", "overdue", "due_next_7_days")))

        resp = client.get("/wrong-questions?size=5", headers=headers)
        check("错题本列表", resp.status_code == 200 and len(resp.json()["items"]) > 0)
        wrong_items = resp.json()["items"]
        first_wrong = wrong_items[0]
        check("错题含排期信息", "days_until_due" in first_wrong and "error_count" in first_wrong)

        # 首次入本间隔 1 天（明天才到期），当前无到期错题应明确报错
        resp = client.post("/wrong-questions/review/generate", json={"count": 5}, headers=headers)
        check("无到期错题时组卷明确报错", resp.status_code == 400 and "到期" in resp.json()["detail"], resp.text[:100])

        resp = client.post(f"/wrong-questions/{first_wrong['id']}/master", headers=headers)
        check("标记掌握", resp.status_code == 200)
        resp = client.get("/wrong-questions/stats", headers=headers)
        check("掌握后错题数减一", resp.json()["total"] == stats["total"] - 1)

        resp = client.delete(f"/wrong-questions/{wrong_items[1]['id']}", headers=headers)
        check("移出错题本", resp.status_code == 200)

        # ---------- 6. 分析看板 ----------
        print("[6] 分析看板")
        resp = client.get("/analytics/questions/overview", headers=headers)
        ov = resp.json()
        check("题目总览", ov["total"] > 0 and len(ov["by_type"]) == 3 and len(ov["by_difficulty"]) == 3)

        resp = client.get("/analytics/questions/accuracy?limit=5", headers=headers)
        check("正确率排行", resp.status_code == 200)

        resp = client.get("/analytics/practice/overview", headers=headers)
        po = resp.json()
        check("做题总览", po["session_count"] >= 1 and po["total_answered"] > 0)

        resp = client.get("/analytics/practice/trend?days=30", headers=headers)
        check("成绩趋势", resp.status_code == 200 and len(resp.json()["items"]) > 0)

        resp = client.get("/analytics/practice/by-type", headers=headers)
        check("分题型正确率", resp.status_code == 200 and len(resp.json()["items"]) > 0)

        resp = client.get("/analytics/practice/recent?limit=5", headers=headers)
        check("最近考试", resp.status_code == 200)

        # ---------- 7. 系统配置 ----------
        print("[7] 系统配置")
        resp = client.get("/settings", headers=headers)
        check("获取系统配置", resp.status_code == 200 and "llm_enabled" in resp.json(), resp.text[:100])
        check("API Key 脱敏返回", "****" in resp.json()["llm_api_key_masked"] or resp.json()["llm_api_key_set"] is False)

        # 只读写非敏感字段（超时时间）验证配置持久化，测试后恢复原值。
        # 不修改 base_url/key/model，也不调用 /settings/reset —— 这些会污染真实 LLM 配置且 Key 无法恢复明文。
        base_cfg = client.get("/settings", headers=headers).json()
        original_timeout = base_cfg["llm_timeout_seconds"]
        resp = client.put(
            "/settings",
            json={"llm_timeout_seconds": 130},
            headers=headers,
        )
        check(
            "保存配置（即时生效）",
            resp.status_code == 200 and resp.json()["llm_timeout_seconds"] == 130,
            resp.text[:100],
        )

        resp = client.get("/settings", headers=headers)
        check("配置已持久化", resp.json()["llm_timeout_seconds"] == 130)

        # 恢复原超时配置
        client.put("/settings", json={"llm_timeout_seconds": original_timeout}, headers=headers)

        resp = client.post("/settings/test", json={"target": "llm"}, headers=headers)
        check(
            "测试连接返回结构化结果（不会崩溃）",
            resp.status_code == 200 and "ok" in resp.json() and "latency_ms" in resp.json(),
            resp.text[:120],
        )

        resp = client.post(
            "/settings/password",
            json={"old_password": "wrong-old", "new_password": "newpass123"},
            headers=headers,
        )
        check("原密码错误被拒绝", resp.status_code == 400)

        # ---------- 7.5 AI 讲题 ----------
        print("[7.5] AI 讲题")
        target_qid = gen["created"][0]["id"]
        resp = client.post("/chat/sessions", json={"question_id": target_qid}, headers=headers)
        check("创建讲题会话", resp.status_code == 201, resp.text[:100])
        chat_sid = resp.json()["id"]

        # 按 LLM 配置状态分支断言：已配置 → 真实 SSE 流式回复；未配置 → 明确拒绝并引导
        llm_on = client.get("/settings", headers=headers).json()["llm_enabled"]
        resp = client.post(
            f"/chat/sessions/{chat_sid}/messages",
            json={"content": "请讲解这道题"},
            headers=headers,
            timeout=180,
        )
        if llm_on:
            check(
                "讲题 SSE 流式返回",
                resp.status_code == 200
                and "text/event-stream" in resp.headers.get("content-type", ""),
                resp.text[:100],
            )
            check(
                "SSE 事件包含正文增量与结束标记",
                'data: {"type": "chunk"' in resp.text or '"type":"chunk"' in resp.text,
                resp.text[:100],
            )
        else:
            check(
                "未配置 LLM 时发送明确拒绝并引导配置",
                resp.status_code == 400 and "LLM" in resp.json()["detail"],
                resp.text[:100],
            )

        resp = client.get(f"/chat/sessions/{chat_sid}/messages", headers=headers)
        check("讲题历史消息", resp.status_code == 200 and isinstance(resp.json(), list))

        resp = client.get(f"/chat/sessions?question_id={target_qid}", headers=headers)
        check("题目会话列表", resp.status_code == 200 and len(resp.json()) >= 1)

        # ---------- 7.6 检索与评测 ----------
        print("[7.6] 混合检索与评测")
        resp = client.get("/retrieval/overview", headers=headers)
        check(
            "检索评测概览",
            resp.status_code == 200 and resp.json()["chunk_count"] >= 1,
            resp.text[:120],
        )

        # 三种模式都能检索（强制用关键词模式跑，避免依赖 embedding 配置）
        for mode, expect_channel in (("hybrid", None), ("bm25", "bm25"), ("vector", "vector")):
            resp = client.post(
                "/knowledge/search",
                json={"query": "缓存 协商 ETag", "top_k": 3, "mode": mode},
                headers=headers,
            )
            body = resp.json() if resp.status_code == 200 else {}
            ok = resp.status_code == 200 and body.get("mode") == mode
            if expect_channel and body.get("results"):
                ok = ok and expect_channel in body["results"][0]["channels"]
            check(f"检索模式 {mode}", ok, resp.text[:120])

        resp = client.post(
            "/knowledge/search", json={"query": "缓存", "mode": "unknown"}, headers=headers
        )
        check("非法模式回落为 hybrid", resp.status_code == 200 and resp.json()["mode"] == "hybrid")

        resp = client.post("/retrieval/cases/auto", json={"count": 3, "use_llm": False}, headers=headers)
        check("自动生成评测集", resp.status_code == 200 and resp.json()["created"] >= 1, resp.text[:120])

        resp = client.get("/retrieval/cases", headers=headers)
        cases = resp.json() if resp.status_code == 200 else []
        check("评测集列表", resp.status_code == 200 and len(cases) >= 1)
        check(
            "评测用例含期望块",
            bool(cases) and len(cases[0]["expected_ids"]) >= 1 and bool(cases[0]["expected_preview"]),
            str(cases[:1])[:120],
        )

        resp = client.post(
            "/retrieval/run",
            json={"top_k": 5, "use_rewrite": True, "vector_weight": 1.0},
            headers=headers,
        )
        run = resp.json() if resp.status_code == 200 else {}
        check("运行检索评测", resp.status_code == 200 and run.get("case_count", 0) >= 1, resp.text[:120])
        check(
            "三档基线指标齐全",
            {"vector", "bm25", "hybrid"}.issubset(set(run.get("summary", {}))),
            str(run.get("summary"))[:160],
        )
        check(
            "指标取值合法(0~1)",
            all(
                0.0 <= m[k] <= 1.0
                for m in run.get("summary", {}).values()
                for k in ("recall", "mrr", "hit_at_1")
            ),
            str(run.get("summary"))[:160],
        )
        check(
            "逐用例明细可下钻",
            isinstance(run.get("detail"), list) and bool(run["detail"][0]["modes"]["hybrid"]["ranked"] is not None),
            str(run.get("detail"))[:120],
        )

        resp = client.post(
            "/retrieval/run",
            json={"top_k": 5, "use_rewrite": False, "vector_weight": 0.5},
            headers=headers,
        )
        check(
            "融合权重被记录",
            resp.status_code == 200 and resp.json()["vector_weight"] == 0.5,
            resp.text[:120],
        )
        check(
            "不开启改写时少一档",
            "hybrid+rewrite" not in resp.json()["summary"],
            str(resp.json().get("summary"))[:120],
        )

        resp = client.get("/retrieval/runs?limit=5", headers=headers)
        check("评测历史", resp.status_code == 200 and len(resp.json()) >= 2)

        run_id = resp.json()[0]["id"]
        resp = client.get(f"/retrieval/runs/{run_id}", headers=headers)
        check("评测明细详情", resp.status_code == 200 and "summary" in resp.json())

        # 手工录入 + 删除
        chunk_id = client.get("/retrieval/chunks", headers=headers).json()[0]["chunk_id"]
        resp = client.post(
            "/retrieval/cases",
            json={"query": "强缓存和协商缓存的区别", "expected_ids": [chunk_id], "note": "smoke"},
            headers=headers,
        )
        check("手工新增评测用例", resp.status_code == 201, resp.text[:120])
        manual_id = resp.json()["id"] if resp.status_code == 201 else 0
        resp = client.delete(f"/retrieval/cases/{manual_id}", headers=headers)
        check("删除评测用例", resp.status_code == 200)

        resp = client.post(
            "/retrieval/cases", json={"query": "不存在的块", "expected_ids": [999999]}, headers=headers
        )
        check("期望块不存在被拒绝(400)", resp.status_code == 400, resp.text[:120])

        resp = client.delete("/retrieval/cases", headers=headers)
        check("清空评测集", resp.status_code == 200 and resp.json()["deleted"] >= 1, resp.text[:120])
        check(
            "清空后用例为 0",
            client.get("/retrieval/cases", headers=headers).json() == [],
        )

        # ---------- 7.7 掌握度与定向训练 ----------
        print("[7.7] 掌握度与定向训练")
        resp = client.get("/mastery/overview", headers=headers)
        ov = resp.json() if resp.status_code == 200 else {}
        check(
            "掌握度概览",
            resp.status_code == 200 and ov.get("total_answered", 0) >= 1,
            resp.text[:120],
        )
        check(
            "综合掌握度取值合法(0~1)",
            0.0 <= ov.get("overall_mastery", -1) <= 1.0 and 0.0 <= ov.get("confidence", -1) <= 1.0,
            str(ov)[:160],
        )

        for dim, expect in (("q_type", {"choice", "fill", "judge"}), ("difficulty", {"easy", "medium", "hard"})):
            resp = client.get(f"/mastery/dimensions?dim={dim}", headers=headers)
            items = resp.json().get("items", []) if resp.status_code == 200 else []
            keys = {i["key"] for i in items}
            check(
                f"维度掌握度 {dim}",
                resp.status_code == 200 and expect.issubset(keys) and len(items) == 3,
                resp.text[:120],
            )
            check(
                f"{dim} 各项均含掌握度与置信度",
                all(0.0 <= i["mastery"] <= 1.0 and 0.0 <= i["confidence"] <= 1.0 for i in items),
                str(items)[:160],
            )

        resp = client.get("/mastery/dimensions?dim=entry", headers=headers)
        entry_items = resp.json().get("items", []) if resp.status_code == 200 else []
        check(
            "资料维度含已录入资料",
            resp.status_code == 200 and any(i["label"] for i in entry_items),
            resp.text[:120],
        )
        check(
            "未观测维度掌握度为中性 0.5",
            all(i["mastery"] == 0.5 for i in entry_items if i["answered"] == 0),
            str(entry_items)[:160],
        )

        resp = client.get("/mastery/dimensions?dim=bogus", headers=headers)
        check("非法维度被拒绝(422)", resp.status_code == 422, resp.text[:120])

        resp = client.get("/mastery/radar", headers=headers)
        radar = resp.json() if resp.status_code == 200 else {}
        check(
            "雷达 6 轴（题型+难度）",
            len(radar.get("indicators", [])) == 6 and len(radar.get("values", [])) == 6,
            resp.text[:120],
        )
        check(
            "雷达取值合法(0~100)",
            all(0.0 <= v <= 100.0 for v in radar.get("values", [])),
            str(radar.get("values"))[:120],
        )

        resp = client.get("/mastery/weak-points?threshold=0.6", headers=headers)
        weak = resp.json() if resp.status_code == 200 else {}
        check("薄弱项列表", resp.status_code == 200 and "items" in weak, resp.text[:120])
        check(
            "薄弱项均低于阈值且有题可练",
            all(i["mastery"] < 0.6 and i["question_count"] > 0 for i in weak.get("items", [])),
            str(weak.get("items"))[:160],
        )

        # 定向组卷：用「题型-单选」维度（前面已组卷并作答，样本足够）
        resp = client.post(
            "/exams/targeted",
            json={"dim": "q_type", "key": "choice", "count": 2, "types": ["choice"]},
            headers=headers,
        )
        tp = resp.json() if resp.status_code == 200 else {}
        check("定向组卷", resp.status_code == 200 and tp.get("question_count") == 2, resp.text[:160])
        check(
            "定向卷标注来源维度",
            tp.get("config", {}).get("mode") == "targeted" and tp.get("config", {}).get("dim") == "q_type",
            str(tp.get("config"))[:160],
        )
        check("定向卷标题含掌握度", "掌握度" in tp.get("title", ""), tp.get("title", ""))

        # 库存不足：限定到本次冒烟新建的资料（题目数远小于 50），应明确报错而不是静默截断
        resp = client.post(
            "/exams/targeted",
            json={"dim": "entry", "key": str(entry_id), "count": 50},
            headers=headers,
        )
        check(
            "定向组卷库存不足明确报错",
            resp.status_code == 400 and "仅" in resp.json()["detail"],
            resp.text[:120],
        )

        resp = client.post(
            "/exams/targeted",
            json={"dim": "q_type", "key": "choice", "count": 999, "types": ["choice"]},
            headers=headers,
        )
        check("题目数量超上限被拒绝(422)", resp.status_code == 422, resp.text[:120])

        resp = client.post(
            "/exams/targeted", json={"dim": "bogus", "key": "x", "count": 1}, headers=headers
        )
        check("非法维度组卷被拒绝(422)", resp.status_code == 422, resp.text[:120])

        # 出题取材：知识点聚焦走混合检索
        resp = client.post(
            "/questions/generate",
            json={
                "entry_id": entry_id,
                "types": ["choice"],
                "count_per_type": 1,
                "focus": "ETag 协商缓存",
            },
            headers=headers,
        )
        gr = resp.json() if resp.status_code == 200 else {}
        check(
            "出题聚焦走混合检索",
            resp.status_code == 200 and gr.get("retrieval", {}).get("used") is True,
            resp.text[:160],
        )
        check(
            "聚焦命中知识块",
            gr.get("retrieval", {}).get("hit_count", 0) >= 1,
            str(gr.get("retrieval"))[:160],
        )
        resp = client.post(
            "/questions/generate",
            json={"entry_id": entry_id, "types": ["judge"], "count_per_type": 1},
            headers=headers,
        )
        check(
            "未聚焦时回退到全篇取材",
            resp.status_code == 200 and resp.json().get("retrieval", {}).get("used") is False,
            resp.text[:160],
        )

        # ---------- 7.8 内置内容（开箱即用） ----------
        print("[7.8] 内置知识库与题库")
        resp = client.get("/questions?source=builtin&size=1", headers=headers)
        builtin_list = resp.json() if resp.status_code == 200 else {}
        check(
            "内置题可筛选",
            resp.status_code == 200 and builtin_list.get("total", 0) >= 200,
            f"total={builtin_list.get('total')}",
        )
        check(
            "内置题自动过审且带来源标记",
            builtin_list["items"]
            and all(q["source"] == "builtin" for q in builtin_list["items"])
            and all(q["review_status"] == "approved" for q in builtin_list["items"]),
            str(builtin_list["items"][0].get("source")) if builtin_list.get("items") else "",
        )
        check(
            "内置题都能关联到知识库条目",
            all(q.get("entry_id") is not None for q in builtin_list.get("items", [])),
            str(builtin_list.get("items"))[:160],
        )

        resp = client.get("/analytics/questions/overview", headers=headers)
        ov2 = resp.json()
        check(
            "统计区分内置/规则/AI 三种来源",
            ov2.get("builtin_count", 0) >= 200
            and ov2["builtin_count"] + ov2["rule_count"] + ov2["llm_count"] == ov2["total"],
            f"builtin={ov2.get('builtin_count')} rule={ov2.get('rule_count')} "
            f"llm={ov2.get('llm_count')} total={ov2.get('total')}",
        )

        resp = client.get("/knowledge/entries?page=1&size=100", headers=headers)
        entries = resp.json() if resp.status_code == 200 else {}
        builtin_entries = [e for e in entries.get("items", []) if e["source_type"] == "builtin"]
        check(
            "内置知识库语料已就绪",
            len(builtin_entries) >= 15 and all(e["chunk_count"] > 0 for e in builtin_entries),
            f"内置资料 {len(builtin_entries)} 篇",
        )

        # ---------- 8. 边界与错误处理 ----------
        print("[8] 边界与错误处理")
        resp = client.post("/knowledge/entries", json={"title": "x", "content": "太短"}, headers=headers)
        check("内容过短被拒绝", resp.status_code == 422)

        resp = client.get("/questions/999999", headers=headers)
        check("不存在资源 404", resp.status_code == 404)

        resp = client.get("/exams/999999", headers=headers)
        check("不存在考卷 404", resp.status_code == 404)

    print(f"\n结果：{passed} 通过，{failed} 失败")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
