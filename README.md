# 面试题录入训练系统（Interview Trainer）

一站式面试训练闭环：**资料录入 → AI 处理分析 → AI 生成题目 → 随机组卷 → 在线答题 → AI 评分 → 数据复盘**。

- 关系数据库：**SQLite**（ORM 建模，改一个配置项即可切 PostgreSQL）
- 向量数据库：**ChromaDB**（嵌入式持久化，语义检索 + 出题去重）
- 检索：**混合检索**（向量 + BM25 + RRF 融合 + 查询改写），内置评测集与 Recall/MRR/Hit@1 量化报告
- 组卷：**难度自适应组卷**（入门 / 夯实 / 均衡 / 冲刺四档蓝图，按比例分配且绝不静默凑数）+ **内置检索评测预置**（约 20 条手写用例随仓库分发，零配置即可量化混合检索收益）
- AI 双通道：配置任意 **OpenAI 兼容 API** 走真实 LLM；不配置则内置**规则引擎**全功能演示
- 前端：React 18 + TypeScript + Vite + AntD 5 + ECharts 5

---

## 1. 快速开始（5 分钟跑通）

### 环境要求
- Python ≥ 3.10（开发验证环境：3.13）
- Node.js ≥ 18（开发验证环境：22）

### 第一步：启动后端

```bash
cd interview-trainer/backend

# 创建虚拟环境并安装依赖（任选其一）
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 写入演示数据（内置 19 篇语料 + 207 道内置题 + 10 条演示资料 + 2 场历史考试）
python seed.py

# 已有演示库需要补充新语料时（不重建、不重新出题）
python seed.py --ensure

# 内置内容扩充后给已有用户补齐（幂等，只补缺失部分）
python seed.py --builtin

# 启动服务（默认 8000 端口）
uvicorn app.main:app --reload --port 8000
```

启动后访问交互式 API 文档：**http://localhost:8000/docs**

### 第二步：启动前端

```bash
cd interview-trainer/frontend
npm install
npm run dev        # 默认 5173 端口，/api 已代理到 8000
```

打开 **http://localhost:5173**，使用演示账号登录：

| 账号 | 密码 |
|---|---|
| `demo` | `demo123` |

> **开箱即用**：不配置 LLM Key 也能直接用——系统自带 19 篇语料与 207 道手写精选题，
> 新用户注册后后台自动载入，组卷、考试、掌握度、检索评测全部可用。
> 自己录资料出题时，没有 Key 走演示模式（内置规则引擎），题目显示「规则生成」徽标；
> 配置 Key 后同一份代码切换为「AI 生成」。

### 一键体验路径

1. **知识库** → 查看 19 篇内置语料 + 8 条演示资料 → 文本/文件（.txt/.md/.pdf/.docx）/网页链接三种方式录入 → 自动分块向量化 → AI 出题
2. **题库** → 207 道内置精选题可直接按题型/难度/**来源**/关键词筛选浏览（已通过/待审核/已拒绝分 Tab）
3. **做题训练** → 配置题量题型 → 「生成考卷」→ 逐题作答 → 提交 → 查看 AI 评分与逐题解析
4. **题目分析** → 题型/难度分布图、收录 Top10、正确率最低 10 题
5. **做题分析** → 成绩趋势、分题型正确率、最近考试记录
6. **系统配置** → 配置 LLM/Embedding、测试连通性、修改密码（见下节）
7. **错题本** → 考试错题自动收入，SM-2 间隔重复排期，到期一键组复习卷
8. **题目审核** → AI 新题进入待审核队列，通过/拒绝/编辑后通过/批量审核后才进入组卷池
9. **AI 讲题** → 结果页/错题本「问 AI」多轮对话讲解（SSE 流式，需配置 LLM；未配置时入口禁用并引导）

---

## 2. 系统配置页（免重启切换 AI 模式）

侧边栏「系统配置」提供 Web UI 配置能力，**保存后即时生效，无需重启服务**：

| 功能 | 说明 |
|---|---|
| LLM 配置 | Base URL / API Key（脱敏展示，留空不修改）/ 模型 / 超时 |
| Embedding 配置 | 可选；不配置则使用内置确定性向量 |
| 测试连接 | 用当前表单内容（含未保存）发起一次最小真实请求，返回耗时与结果 |
| 恢复默认 | 一键清除全部覆盖，回退 `.env` 配置 |
| 账号安全 | 修改密码（需验证原密码） |

配置优先级：**配置页保存值（system_configs 表）> .env > 代码默认值**。不配置 LLM 时系统保持演示模式，功能完整可用。

### 接入真实 LLM（可选）

也可以直接编辑配置文件（与配置页二选一，配置页优先）：复制 `backend/.env.example` 为 `backend/.env`，填入任意 **OpenAI 兼容协议**服务：

| 服务商 | Base URL | 模型 |
|---|---|---|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| **火山方舟 Agent Plan 套餐** | `https://ark.cn-beijing.volces.com/api/plan/v3` | `ark-code-latest` |

> ⚠️ **火山方舟套餐注意**：Agent Plan / Coding Plan 的专属 Key 必须配套餐端点（`/api/plan/v3`），
> 错用标准端点 `/api/v3` 会认证失败且可能产生额外费用。标准方舟 API Key 才用 `/api/v3`。

```ini
# 配置示例（DeepSeek + Embedding）
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-xxxxxxxx
LLM_MODEL=deepseek-chat

# 可选：真实 Embedding（不配则用内置确定性向量，检索/去重仍可用）
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=sk-xxxx
EMBEDDING_MODEL=BAAI/bge-m3
```

已验证兼容：DeepSeek、通义千问（dashscope compatible-mode）、Moonshot、OpenAI。
重启后端后，出题与填空评分自动切换为 LLM 通道（题目徽标显示「AI 生成」）。

---

## 3. 功能架构

```
┌────────────────────────────────────────────────────────────┐
│ 前端 React + AntD + ECharts（5173）                        │
│  知识库 │ 题库 │ 做题训练 │ 考试/结果 │ 题目分析 │ 做题分析   │
│  检索评测 │ 掌握度雷达 │ 系统配置                            │
└───────────────────────┬────────────────────────────────────┘
                        │ HTTP /api（JWT）
┌───────────────────────▼────────────────────────────────────┐
│ FastAPI 后端（8000）                                        │
│  routers: auth / knowledge / questions / exams / analytics │
│           wrong-questions / chat / retrieval / mastery      │
│  services:                                                 │
│    chunker      段落→句读二级切分（300~500 字/块）          │
│    embeddings   API 向量 or 内置确定性向量（中文 n-gram）    │
│    vector_store ChromaDB 封装（kb_chunks / questions）      │
│    bm25/retrieval  BM25 索引 + 混合检索（RRF 融合）          │
│    retrieval_eval  检索评测集构建与 Recall/MRR/Hit@1 度量   │
│    generator    LLM 出题 + 规则引擎降级 + 向量去重           │
│    grader       客观题精确匹配 + 填空语义相似度/LLM 评判     │
│    srs          SM-2 间隔重复排期                            │
│    mastery      掌握度聚合（时间衰减 + 置信度收缩）+ 定向取材 │
│    builtin      内置语料/题库的幂等载入（开箱即用）           │
│    stats        两张分析看板的聚合查询                       │
└──────────────┬──────────────────────┬──────────────────────┘
               │ SQLAlchemy           │ ChromaDB
        ┌──────▼──────┐        ┌──────▼──────┐
        │   SQLite    │        │  向量数据库  │
        │ (关系数据)   │        │ (data/chroma)│
        └─────────────┘        └─────────────┘
```

### 核心流程

| 流程 | 说明 |
|---|---|
| 内置内容（开箱即用） | 内置 19 篇语料 + 207 道手写精选题随仓库分发，注册后后台载入；按「标题 / 题干+条目」幂等去重，内置题自动过审 |
| 录入处理 | 文本/文件录入 → 分块 → 关键词提取 → 向量化 → 入 ChromaDB，状态机 `processing → ready/failed` |
| AI 出题 | 选素材块（可填「知识点聚焦」走混合检索取材）→ LLM（或规则引擎）生成单选/填空/判断 + 标准答案 + 解析 → JSON 修复重试 → **向量去重**（≥0.95 相似度舍弃）→ 入库 |
| 随机组卷 | 按题型组合/难度/来源随机不重复抽样；另支持**难度蓝图自适应组卷**（入门/夯实/均衡/冲刺按比例分配，库存不足回补不静默凑数）；库存不足明确报错 |
| 掌握度与定向训练 | 按资料/题型/难度聚合作答记录（时间衰减 + 置信度收缩）→ 雷达图 + 薄弱项推荐 → 一键定向组卷（错题优先） |
| 在线考试 | 会话级考试，**防抖自动保存草稿**，刷新/退出后续考恢复已填答案 |
| AI 评分 | 选择/判断精确匹配；填空：等价答案包含 → LLM 评判 → 语义相似度分档（≥0.8 满分 / ≥0.5 半分）；逐题反馈 + 总分/得分率/用时 |
| 题目分析 | 总量、AI/规则生成占比、题型分布、难度分布、收录 Top10、正确率最低 10 题 |
| 做题分析 | 考试场次、平均得分率、累计答题、分题型正确率、30 天成绩趋势、最近考试 |

### 数据模型（13 张表）

`users` → `knowledge_entries` → `knowledge_chunks` → `questions`
`exam_papers` → `exam_paper_questions` → `exam_sessions` → `exam_answers`
`wrong_questions`（SM-2）｜ `ai_chat_sessions` → `ai_chat_messages` ｜ `retrieval_eval_cases` → `retrieval_eval_runs`

完整 ER 图、API 契约、技术选型对比见 [`docs/01-需求分析与架构设计.md`](docs/01-需求分析与架构设计.md)。

---

## 4. 质量保障

```bash
cd backend

# 单元测试（169 个）：分块 / 文本相似度 / 评分器 / 规则出题 / SM-2 / 导入 / 讲题 / BM25 / 检索 / 掌握度 / 内置内容 / 难度自适应 / 内置评测预置
python -m pytest

# 全链路 API 冒烟测试（124 项断言，可重复执行）
# 需先启动后端：uvicorn app.main:app --port 8000
python scripts/smoke_test.py

# 浏览器 E2E（需前端 dev server 运行中，见 scripts/e2e_test.js 头部说明）
```

已验证结果（开发环境 Windows + Python 3.13 + Node 22）：

| 验证项 | 结果 |
|---|---|
| `pytest` 单元测试 | **169 passed**（SM-2 13 + 导入解析 10 + 讲题上下文 4 + BM25 7 + 检索 19 + 评测 9 + 掌握度 24 + 内置内容 14 + 难度自适应 8 + 内置评测预置 7） |
| API 冒烟测试（认证/录入/导入/出题/审核/组卷/考试/评分/分析/配置/错题本/讲题/检索评测/掌握度/内置内容/内置评测/边界） | **124/124 通过** |
| 前端 `tsc --noEmit` + `vite build` | **通过，0 错误** |
| 浏览器 E2E（Edge，全页面 + 完整考试 + 审核流 + 导入错误路径 + 讲题 + 检索评测 + 掌握度定向练习 + 内置内容 + 难度蓝图组卷 + 内置评测开箱即用） | **18/18 通过** |

---

## 5. 目录结构

```
interview-trainer/
├── README.md                          # 本文档
├── docs/
│   ├── 01-需求分析与架构设计.md        # 需求/架构/ER/API 契约/选型对比
│   ├── 05-v1.5-检索增强与评测.md
│   ├── 06-v1.6-掌握度与定向训练.md
│   ├── 07-v1.7-内置知识库与题库.md
│   ├── 08-v1.8-难度自适应组卷与内置评测预置.md
│   └── screenshots/                   # E2E 运行截图
├── backend/
│   ├── app/                           # FastAPI 应用（routers/services/models）
│   ├── data/builtin/                  # 内置语料 + 手写精选题库（按技术域分文件）
│   ├── tests/                         # pytest 单元测试
│   ├── scripts/smoke_test.py          # 全链路 API 冒烟测试
│   ├── seed.py                        # 演示数据种子（demo/demo123）
│   ├── requirements.txt
│   └── .env.example                   # LLM/Embedding 配置样例
└── frontend/
    ├── src/pages/                     # 13 个业务页面（含系统配置、检索评测、掌握度）
    └── src/api/                       # axios 客户端 + 类型定义
```

---

## 6. 已知限制与演进方向

**当前版本限制**：
- SQLite 单文件，适合单用户/演示级并发（切 PostgreSQL 只需改 `DATABASE_URL`）
- 文件上传限 `.txt` / `.md` / `.pdf` / `.docx`（≤10MB，PDF 不做 OCR）
- 内置规则引擎出题为术语识别/遮蔽/否定变换，质量低于 LLM（UI 有「规则生成」徽标区分）
- 被考卷引用的题目/资料不可删除（保证历史成绩完整），需先删除对应考卷
- 未配置真实 Embedding 时，内置向量为字符 n-gram 哈希（本质是词法匹配），
  混合检索的收益受限——请用「检索评测」页实测后再决定向量通道权重

**演进路线**：PostgreSQL + pgvector 一体化、Docker Compose 一键部署、Anki 导出、多用户。

---

## 7. 内置内容与演示数据说明

### 内置内容（开箱即用）

系统随仓库分发一套**内置知识库语料 + 手写精选题库**，注册后即可组卷做题，
不需要先录资料、也不依赖 LLM Key。题目按「技术域 → 考点 → 题目」组织，
并通过条目标题关联到语料，因此掌握度、检索、错题本都能直接复用。

| 技术域 | 题量 | 覆盖 |
|---|---|---|
| 后端-Java | 31 | 并发与线程池、锁与 AQS、集合、Spring、JVM |
| 数据库（MySQL + Redis） | 37 | 索引与锁、主从延迟、分库分表、缓存三大问题、热 key、集群容灾 |
| 分布式与架构 | 31 | 限流熔断降级、MQ 幂等与顺序、分布式事务、多活容灾、微服务治理 |
| AI 应用 | 27 | 提示与上下文工程、Agent、评测与回归、RAG / 向量检索 |
| 后端-Python | 18 | GIL、asyncio、性能分析、装饰器与上下文管理器 |
| 计算机基础 | 25 | TCP/HTTP/TLS、操作系统与 IO 多路复用、高频算法 |
| 前端 | 20 | 浏览器渲染与缓存、React 机制、性能优化 |
| 工程运维 | 18 | 容器化与 K8s、可观测性、容量与故障处置 |
| **合计** | **207** | 19 篇语料 |

后端域中高难度题目占比 ≥ 70%，重点考**高并发、容灾、故障排查等生产级经验**
（如无界队列导致线程数卡在 8、主从延迟飙到几十秒、缓存全挂如何止损）。
详细设计见 [`docs/07-v1.7-内置知识库与题库.md`](docs/07-v1.7-内置知识库与题库.md)。

### 演示数据

`seed.py` 另外写入 8 条演示资料与 2 场历史考试：Redis 核心知识、MySQL 索引与事务、
React Hooks 与性能优化、RAG 检索增强生成、HTTP 缓存与浏览器性能、
JavaScript 事件循环、消息队列与分布式事务、Linux 性能排查与容器化。
重新播种：`python seed.py --reset`（清空数据库与向量库）；已入库后补充语料：`python seed.py --ensure`；
补齐内置内容：`python seed.py --builtin`。
