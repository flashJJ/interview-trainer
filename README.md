# 面试题录入训练系统（Interview Trainer）

一站式面试训练闭环：**资料录入 → AI 处理分析 → AI 生成题目 → 随机组卷 → 在线答题 → AI 评分 → 数据复盘**。

- 关系数据库：**SQLite**（ORM 建模，改一个配置项即可切 PostgreSQL）
- 向量数据库：**ChromaDB**（嵌入式持久化，语义检索 + 出题去重）
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

# 写入演示数据（5 条技术知识库 + 45 道题目 + 2 场历史考试）
python seed.py

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

> 没有配置 LLM API Key 时，系统自动进入**演示模式**（内置规则引擎出题/评分），
> 题目上会显示「规则生成」徽标；配置 Key 后同一份代码切换为「AI 生成」。

### 一键体验路径

1. **知识库** → 查看 5 条种子资料 → 点任意条目「AI 出题」（选题型/数量/难度）→ 生成题目
2. **题库** → 按题型/难度/关键词筛选浏览
3. **做题训练** → 配置题量题型 → 「生成考卷」→ 逐题作答 → 提交 → 查看 AI 评分与逐题解析
4. **题目分析** → 题型/难度分布图、收录 Top10、正确率最低 10 题
5. **做题分析** → 成绩趋势、分题型正确率、最近考试记录
6. **系统配置** → 配置 LLM/Embedding、测试连通性、修改密码（见下节）
7. **错题本** → 考试错题自动收入，SM-2 间隔重复排期，到期一键组复习卷

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

```ini
# DeepSeek 示例
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
└───────────────────────┬────────────────────────────────────┘
                        │ HTTP /api（JWT）
┌───────────────────────▼────────────────────────────────────┐
│ FastAPI 后端（8000）                                        │
│  routers: auth / knowledge / questions / exams / analytics │
│  services:                                                 │
│    chunker      段落→句读二级切分（300~500 字/块）          │
│    embeddings   API 向量 or 内置确定性向量（中文 n-gram）    │
│    vector_store ChromaDB 封装（kb_chunks / questions）      │
│    generator    LLM 出题 + 规则引擎降级 + 向量去重           │
│    grader       客观题精确匹配 + 填空语义相似度/LLM 评判     │
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
| 录入处理 | 文本/文件录入 → 分块 → 关键词提取 → 向量化 → 入 ChromaDB，状态机 `processing → ready/failed` |
| AI 出题 | 选素材块 → LLM（或规则引擎）生成单选/填空/判断 + 标准答案 + 解析 → JSON 修复重试 → **向量去重**（≥0.95 相似度舍弃）→ 入库 |
| 随机组卷 | 按题型组合/难度/来源随机不重复抽样，库存不足明确报错 |
| 在线考试 | 会话级考试，**防抖自动保存草稿**，刷新/退出后续考恢复已填答案 |
| AI 评分 | 选择/判断精确匹配；填空：等价答案包含 → LLM 评判 → 语义相似度分档（≥0.8 满分 / ≥0.5 半分）；逐题反馈 + 总分/得分率/用时 |
| 题目分析 | 总量、AI/规则生成占比、题型分布、难度分布、收录 Top10、正确率最低 10 题 |
| 做题分析 | 考试场次、平均得分率、累计答题、分题型正确率、30 天成绩趋势、最近考试 |

### 数据模型（8 张表）

`users` → `knowledge_entries` → `knowledge_chunks` → `questions`
`exam_papers` → `exam_paper_questions` → `exam_sessions` → `exam_answers`

完整 ER 图、API 契约、技术选型对比见 [`docs/01-需求分析与架构设计.md`](docs/01-需求分析与架构设计.md)。

---

## 4. 质量保障

```bash
cd backend

# 单元测试（41 个）：分块 / 文本相似度 / 评分器 / 规则出题
python -m pytest

# 全链路 API 冒烟测试（45 项断言，可重复执行）
# 需先启动后端：uvicorn app.main:app --port 8000
python scripts/smoke_test.py

# 浏览器 E2E（需前端 dev server 运行中，见 scripts/e2e_test.js 头部说明）
```

已验证结果（开发环境 Windows + Python 3.13 + Node 22）：

| 验证项 | 结果 |
|---|---|
| `pytest` 单元测试 | **67 passed**（含 13 个 SM-2 算法用例） |
| API 冒烟测试（认证/录入/出题/组卷/考试/评分/分析/配置/错题本/边界） | **60/60 通过** |
| 前端 `tsc --noEmit` + `vite build` | **通过，0 错误** |
| 浏览器 E2E（Edge，登录→各页面→完整考试评分→配置页→错题本） | **10/10 通过，控制台 0 错误** |

---

## 5. 目录结构

```
interview-trainer/
├── README.md                          # 本文档
├── docs/
│   ├── 01-需求分析与架构设计.md        # 需求/架构/ER/API 契约/选型对比
│   └── screenshots/                   # E2E 运行截图
├── backend/
│   ├── app/                           # FastAPI 应用（routers/services/models）
│   ├── tests/                         # pytest 单元测试
│   ├── scripts/smoke_test.py          # 全链路 API 冒烟测试
│   ├── seed.py                        # 演示数据种子（demo/demo123）
│   ├── requirements.txt
│   └── .env.example                   # LLM/Embedding 配置样例
└── frontend/
    ├── src/pages/                     # 8 个业务页面（含系统配置）
    └── src/api/                       # axios 客户端 + 类型定义
```

---

## 6. 已知限制与演进方向

**当前版本限制**：
- SQLite 单文件，适合单用户/演示级并发（切 PostgreSQL 只需改 `DATABASE_URL`）
- 文件上传限 `.txt` / `.md`（UTF-8，≤5MB）
- 内置规则引擎出题为术语识别/遮蔽/否定变换，质量低于 LLM（UI 有「规则生成」徽标区分）
- 被考卷引用的题目/资料不可删除（保证历史成绩完整），需先删除对应考卷

**演进路线**：PostgreSQL + pgvector 一体化、出题人工审核流、错题本 + SM-2 间隔重复、PDF/DOCX 导入、Anki 导出、LLM 对话式讲题。

---

## 7. 演示数据说明

`seed.py` 写入的内容同时可作为面试复习材料：Redis 核心知识、MySQL 索引与事务、
React Hooks 与性能优化、RAG 检索增强生成、Python 装饰器与上下文管理器。
重新播种：`python seed.py --reset`（清空数据库与向量库）。
