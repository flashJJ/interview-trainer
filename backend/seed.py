"""演示数据种子脚本。

用法：
    python seed.py            # 写入演示数据（幂等，已存在 demo 用户则跳过）
    python seed.py --reset    # 清空数据库与向量库后重新播种
    python seed.py --builtin  # 只补内置知识库与内置题库（幂等，不动已有数据）
    python seed.py --ensure   # 只补 KNOWLEDGE_ENTRIES 中缺失的资料

「开箱即用」的关键在内置内容：内置知识库语料 + 手写精选题库随仓库分发，
不配置 LLM Key 也能拥有一套覆盖面完整、质量稳定的资料与题目。

默认账号：demo / demo123
"""

import json
import random
import sys
from datetime import datetime, timedelta

import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal, engine, init_db
from app.models import (
    ExamPaper,
    ExamPaperQuestion,
    ExamSession,
    KnowledgeChunk,
    KnowledgeEntry,
    Question,
    User,
)
from app.security import hash_password
from app.services.generator import (
    ChunkLike,
    QuestionGenerator,
    persist_drafts,
    refresh_entry_question_counts,
)
from app.services.grader import Grader, grade_and_submit_session
from app.services.pipeline import process_entry
from app.services.runtime import get_embeddings, get_llm, get_vector_store

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"

KNOWLEDGE_ENTRIES = [
    (
        "Redis 核心知识笔记",
        """Redis 是一个开源的基于内存的高性能键值数据库，支持多种数据结构：字符串 String、哈希 Hash、列表 List、集合 Set、有序集合 ZSet，以及 Bitmap、HyperLogLog、Geo 等扩展类型。

单线程模型：Redis 的网络 IO 和命令执行采用单线程（Redis 6.0 引入多线程 IO），避免了多线程上下文切换和锁竞争，这是其高性能的核心原因之一。

持久化有两种方式：RDB 是某一时刻的内存快照，文件小、恢复快，但可能丢失最后一次快照之后的数据；AOF 记录每条写命令，可靠性更高，支持 everysec 每秒刷盘策略，文件较大且需要重写压缩。

过期策略采用惰性删除加定期删除：访问键时检查是否过期，同时后台每隔一段时间随机抽查一批键并删除过期键。内存淘汰策略包括 noeviction、volatile-lru、allkeys-lru、allkeys-random 等，缓存场景常用 allkeys-lru。

三大缓存问题：缓存穿透指查询根本不存在的数据，请求全部打到数据库，可用布隆过滤器或缓存空值解决；缓存击穿指热点键过期瞬间大量请求同时打到数据库，可用互斥锁或逻辑过期解决；缓存雪崩指大量键同时过期或 Redis 整体宕机，可用随机 TTL、多级缓存和高可用集群应对。

高可用架构：主从复制实现数据冗余与读写分离，哨兵模式实现自动故障转移，Redis Cluster 通过数据分片实现横向扩展，是生产环境的主流方案。""",
    ),
    (
        "MySQL 索引与事务",
        """MySQL InnoDB 使用 B+ 树作为索引结构，非叶子节点只存储键值，叶子节点之间通过双向链表连接，适合范围查询和排序。聚簇索引的叶子节点存储整行数据，二级索引的叶子节点存储主键值，回表查询需要再查一次聚簇索引。

最左前缀原则：联合索引 (a, b, c) 相当于建立了 (a)、(a, b)、(a, b, c) 三个索引，查询条件必须从索引最左列开始并且不能跳过中间列，才能有效使用联合索引。

覆盖索引指查询列全部包含在索引中，无需回表，可以显著提升查询性能。索引下推将 WHERE 条件下推到存储引擎层进行过滤，减少回表次数。

事务四大特性 ACID：原子性通过 undo log 实现，持久性通过 redo log 实现，隔离性通过 MVCC 和锁实现，一致性是最终目标。

隔离级别从低到高分为：读未提交、读已提交、可重复读、串行化。MySQL 默认可重复读，通过 MVCC 解决了幻读的大部分场景，间隙锁进一步防止幻读。

MVCC 依赖隐藏字段、undo log 版本链和 ReadView：每行数据都有事务 ID 和回滚指针，快照读根据 ReadView 判断版本可见性。当前读则读取最新提交版本并加锁。

死锁的四个必要条件：互斥、请求与保持、不可剥夺、循环等待。处理方法包括设置锁等待超时、按固定顺序访问表和行、拆分大事务、适当降低隔离级别。""",
    ),
    (
        "React Hooks 与性能优化",
        """useState 用于在函数组件中添加状态，setState 是异步批处理的，同一次事件循环中的多次调用会合并渲染。useEffect 处理副作用，第二个参数是依赖数组，空数组表示只在挂载和卸载时执行，返回清理函数可以避免闭包陷阱和重复订阅。

useMemo 缓存计算结果，useCallback 缓存函数引用，用于避免子组件因 props 引用变化而无效重渲染。但过度使用反而增加开销，应当配合 React.memo 按需优化。

React 的虚拟 DOM 是用 JS 对象描述的 UI 结构，状态变化后生成新的虚拟 DOM，通过 Diff 算法与旧树对比，最小化真实 DOM 更新。Diff 采用同层比较策略，通过 key 标识列表元素身份，使用稳定唯一的 key 可以避免错误的节点复用。

渲染性能优化手段：代码分割与懒加载使用 React.lazy 和 Suspense；长列表使用虚拟滚动；不可变数据配合 memo 减少比较成本；避免在渲染函数中创建新对象和新函数。

并发特性：useTransition 将非紧急更新标记为过渡任务，useDeferredValue 延迟渲染昂贵部分，保持输入框响应灵敏。Suspense 支持数据获取过程中的加载态展示。

常见陷阱：在 useEffect 中遗漏依赖导致闭包捕获过期值；直接修改 state 违背不可变性；用数组 index 作为动态列表的 key 导致组件状态错乱。""",
    ),
    (
        "RAG 检索增强生成基础",
        """RAG 是检索增强生成的缩写，核心流程是：文档加载与解析、文本切分、向量化嵌入、存入向量数据库；提问时先检索相关片段，再把片段作为上下文交给大模型生成答案。

文档切分策略直接影响检索质量：固定长度切分简单但可能切断语义，按标题和段落等文档结构切分更加合理，语义切分利用嵌入相似度在话题转换处下刀。切分块之间通常保留重叠窗口，避免边界信息丢失。

检索环节常用混合检索：向量检索擅长语义相似匹配，BM25 关键词检索擅长精确词匹配，两者结果融合可以提升召回率。重排模型对初检结果进行精细排序，进一步筛选出高相关片段。

Embedding 模型把文本映射为稠密向量，语义相近的文本向量距离更近。常用中文模型包括 BAAI/bge 系列，检索质量与向量维度、模型训练数据的领域匹配度相关。

生成环节的提示词工程：要求模型仅基于检索到的资料回答，资料不足时明确说明不知道，并给出引用来源，可以显著减少幻觉。

RAG 的评估维度包括检索召回率、答案忠实度、答案相关性和端到端延迟。常见优化方向有查询改写、假设性文档嵌入、多路召回和自我反思纠错。""",
    ),
    # 注：「Python 装饰器与上下文管理器」「JVM 内存模型与垃圾回收」已并入内置语料
    # （data/builtin/knowledge.py），不再在种子脚本里重复录入，避免同名内容冲突。
    (
        "HTTP 缓存与浏览器性能",
        """HTTP 缓存分为强缓存和协商缓存。强缓存由 Cache-Control 的 max-age 和 Expires 控制，命中时浏览器直接使用本地副本，不发请求；协商缓存由 ETag 配合 If-None-Match、Last-Modified 配合 If-Modified-Since 控制，命中时服务端返回 304，只节省响应体流量。

Cache-Control 常用指令：no-store 完全不缓存，no-cache 强制走协商缓存，public 允许代理服务器缓存，private 只允许浏览器缓存，immutable 表示资源内容永不变化可以长期缓存。前端工程里 HTML 通常设置为 no-cache，而带内容哈希的静态资源设置为一年加上 immutable。

CDN 的原理是把静态资源分发到离用户最近的边缘节点，通过 DNS 调度或 Anycast 把请求引导到最优节点。CDN 回源指边缘节点未命中缓存时向上层或源站取数据，回源率高会拖慢响应并增加源站压力。

浏览器的关键渲染路径：解析 HTML 构建 DOM 树，解析 CSS 构建 CSSOM，两者合并为渲染树，再经过布局计算几何位置、绘制生成图层、合成输出到屏幕。CSS 是阻塞渲染的资源，JavaScript 是阻塞解析的资源，因此脚本通常放在底部或加 defer、async。

性能指标方面，首字节时间 TTFB 反映服务端处理速度，首次内容绘制 FCP 和最大内容绘制 LCP 反映加载体验，首次输入延迟 FID 与交互到下次绘制 INP 反映交互流畅度，累积布局偏移 CLS 反映视觉稳定性。

减少重排与重绘的手段：批量修改 DOM、使用 transform 和 opacity 做动画、避免频繁读取会触发强制同步布局的属性如 offsetHeight，必要时用 requestAnimationFrame 合并多次修改。""",
    ),
    (
        "JavaScript 事件循环与异步",
        """JavaScript 是单线程语言，通过事件循环实现并发。调用栈执行同步代码，遇到异步任务时交给宿主环境处理，完成后把回调放入任务队列，调用栈清空后事件循环按规则取出回调执行。

任务分为宏任务和微任务。宏任务包括 setTimeout、setInterval、I/O 回调、UI 渲染；微任务包括 Promise 的 then、queueMicrotask、MutationObserver。每执行完一个宏任务，会清空当前所有微任务队列，然后才进入下一个宏任务，因此微任务总是先于下一个宏任务执行。

Promise 有三种状态：pending、fulfilled、rejected，状态一旦改变就不可逆。then 返回新的 Promise 支持链式调用，catch 捕获链路上任意一环的错误，finally 无论成功失败都会执行。

async 函数返回 Promise，await 会暂停当前函数并把后续代码包装成微任务，让出调用栈给其他任务。await 后面跟非 Promise 值也会异步执行，这一点容易造成时序误判。

Promise.all 全部成功才成功、有一个失败就立即失败；Promise.allSettled 等待全部结束并返回每项状态；Promise.race 返回最先结束的结果；Promise.any 返回最先成功的结果。

常见异步陷阱：在 for 循环中用 var 声明循环变量导致回调拿到最终值；for 循环里依次 await 会串行执行拖慢总耗时，应改用 Promise.all 并发；未捕获的 Promise 拒绝会导致进程警告甚至退出。""",
    ),
    (
        "消息队列与分布式事务",
        """消息队列用于系统解耦、异步处理和流量削峰。生产者发送消息到 Broker，消费者按订阅关系拉取消息处理，Broker 负责持久化与重投。

投递语义有三档：最多一次可能丢消息，至少一次可能重复，恰好一次实现成本极高。工程上通常选择至少一次加消费端幂等来逼近恰好一次的效果。

幂等设计常见方案：用业务唯一键做数据库唯一索引，重复插入直接失败；用 Redis 记录已处理的业务 ID 并设置合理过期时间；用状态机限制流转，只有特定前置状态才能推进，重复消息因状态不匹配被忽略。

消息重复的成因包括生产者重试、Broker 重投、消费者处理超时后重新入队，因此幂等是消费端的必备能力而不是可选项。

消息顺序性：全局有序需要单分区单消费者，代价是吞吐受限；业务上更常见的是按业务主键哈希到同一分区保证局部有序。

堆积处理：先定位是消费能力不足还是消费逻辑阻塞，短期可以扩容消费者并提高并发度，长期要优化慢查询、批量写入和下游依赖超时设置。死信队列用于收纳反复失败的消息，避免阻塞正常消费。

分布式事务的常见方案：两阶段提交强一致但性能和可用性差；TCC 通过业务层的 Try、Confirm、Cancel 补偿；本地消息表把业务操作和消息写入放在同一个本地事务里，再由定时任务投递；事务消息由消息中间件保证半消息与本地事务的最终一致。""",
    ),
    (
        "Linux 性能排查与容器化",
        """性能排查遵循自顶向下的顺序：先看整体负载，再定位是 CPU、内存、磁盘还是网络瓶颈，最后深入到进程和线程。

平均负载 load average 表示运行队列和不可中断睡眠进程的数量，超过 CPU 核数说明存在排队。但负载高不一定是 CPU 问题，大量磁盘 IO 阻塞同样会推高负载。

CPU 排查使用 top 或 htop 观察用户态与内核态占比：用户态高说明业务计算密集，内核态高常见于频繁系统调用或上下文切换；使用 pidstat 定位具体线程，用 perf 采样火焰图找到热点函数。

内存排查看 free 的 available 而不是 free 列，buffers 与 cached 是可回收的。使用 vmstat 观察 si 与 so 判断是否发生换页，一旦频繁换页性能会断崖式下降。

磁盘 IO 使用 iostat 观察 util 使用率与 await 平均等待时间，使用 iotop 定位写盘最多的进程；顺序读写远快于随机读写，机械盘上随机 IO 尤其昂贵。

网络排查：ss 或 netstat 查看连接状态与队列，大量 TIME_WAIT 说明短连接过多应改用连接池，大量 CLOSE_WAIT 说明应用没正确关闭连接；抓包用 tcpdump 配合 Wireshark 分析。

容器化方面，镜像分层机制要求把变化频繁的层放在后面以命中缓存，多阶段构建可以把编译环境与运行环境分离从而显著减小镜像体积。资源限制通过 cgroup 实现，CPU 用 shares 表示相对权重、quota 表示绝对上限，内存超限会触发 OOM Killer。健康检查分存活探针与就绪探针，前者失败触发重启，后者失败只摘除流量。""",
    ),
]

_TABLES = (
    "exam_answers",
    "exam_paper_questions",
    "exam_sessions",
    "exam_papers",
    "questions",
    "knowledge_chunks",
    "knowledge_entries",
    "users",
)


def reset_all() -> None:
    """清空关系库与向量库（--reset 专用）。表结构整体重建以兼容 schema 变更。"""
    from app import models

    with engine.begin() as conn:
        for table in _TABLES:
            conn.execute(text(f"DELETE FROM {table}"))
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    settings = get_settings()
    client = chromadb.PersistentClient(
        path=settings.chroma_dir,
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
    )
    for collection in client.list_collections():
        client.delete_collection(collection.name)
    print("[reset] 数据库与向量库已清空")


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == DEMO_USERNAME).first() is not None:
            print(f"[seed] 用户 {DEMO_USERNAME} 已存在，跳过（如需重来请使用 --reset）")
            return

        random.seed(42)
        user = User(
            username=DEMO_USERNAME,
            email="demo@example.com",
            password_hash=hash_password(DEMO_PASSWORD),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[seed] 创建演示用户 {DEMO_USERNAME} / {DEMO_PASSWORD}")

        # 1) 录入知识库并自动处理（分块 + 关键词 + 向量化）
        entries = []
        for title, content in KNOWLEDGE_ENTRIES:
            entry = KnowledgeEntry(
                user_id=user.id,
                title=title,
                source_type="text",
                content=content,
                status="processing",
                char_count=len(content),
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            process_entry(db, entry)
            db.refresh(entry)
            entries.append(entry)
            print(f"[seed] 知识库「{title}」：{entry.chunk_count} 块，状态 {entry.status}")

        # 1.5) 内置内容：补充内置知识库语料 + 手写精选题库（开箱即用的关键）
        from app.services.builtin import load_builtin

        stat = load_builtin(db, user.id)
        print(
            f"[seed] 内置知识库：新增 {stat['knowledge']['created']} 篇、"
            f"跳过 {stat['knowledge']['skipped']} 篇；"
            f"内置题库：新增 {stat['questions']['created']} 道、"
            f"跳过 {stat['questions']['skipped']} 道"
            + (f"（{stat['questions']['orphan']} 道未关联到条目）" if stat["questions"]["orphan"] else "")
        )

        # 2) AI 出题（无 API Key 时为规则引擎模式）
        generator = QuestionGenerator(
            llm=get_llm(), embeddings=get_embeddings(), vector_store=get_vector_store()
        )
        all_questions: list[Question] = []
        for entry in entries:
            chunks = (
                db.query(KnowledgeChunk)
                .filter(KnowledgeChunk.entry_id == entry.id)
                .order_by(KnowledgeChunk.seq)
                .all()
            )
            chunk_likes = [
                ChunkLike(id=c.id, content=c.content, entry_id=c.entry_id) for c in chunks
            ]
            outcome = generator.generate(
                chunk_likes,
                types=["choice", "fill", "judge"],
                count_per_type=3,
                difficulty=None,
                user_id=user.id,
            )
            if outcome.drafts:
                all_questions.extend(
                    persist_drafts(
                        db, user.id, outcome.drafts, get_embeddings(), get_vector_store(),
                        review_status="approved",  # 种子题目直接通过审核
                    )
                )
                refresh_entry_question_counts(db, [entry.id])
            print(f"[seed] 「{entry.title}」出题 {len(outcome.drafts)} 道（{outcome.mode} 模式）")

        # 3) 两场已提交考试，供分析看板演示
        grader = Grader(llm=get_llm(), embeddings=get_embeddings())
        papers_config = [
            ("首次全科测验", 10, 0.8),
            ("第二轮强化训练", 8, 0.55),
        ]
        for idx, (paper_title, count, accuracy) in enumerate(papers_config):
            pool = [q for q in all_questions if q.q_type in ("choice", "fill", "judge")]
            random.shuffle(pool)
            chosen = pool[:count]
            if len(chosen) < count:
                print(f"[seed] 题库不足，跳过考卷「{paper_title}」")
                continue
            paper = ExamPaper(
                user_id=user.id,
                title=paper_title,
                question_count=len(chosen),
                config=json.dumps({"seed": True}, ensure_ascii=False),
            )
            db.add(paper)
            db.flush()
            for order, question in enumerate(chosen):
                db.add(ExamPaperQuestion(paper_id=paper.id, question_id=question.id, order=order))
            db.commit()
            db.refresh(paper)

            started_at = datetime.utcnow() - timedelta(days=6 - idx * 2, hours=2)
            session = ExamSession(
                user_id=user.id,
                paper_id=paper.id,
                status="in_progress",
                started_at=started_at,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            # 模拟一个准确率为 accuracy 的考生
            answers_map = {}
            for question in chosen:
                if random.random() < accuracy:
                    answers_map[question.id] = question.answer
                elif question.q_type == "choice":
                    answers_map[question.id] = random.choice(
                        [letter for letter in "ABCD" if letter != question.answer]
                    )
                elif question.q_type == "judge":
                    answers_map[question.id] = (
                        "错误" if question.answer == "正确" else "正确"
                    )
                else:
                    answers_map[question.id] = "一个不完全相关的答案"
            result = grade_and_submit_session(db, session, answers_map, grader)
            print(
                f"[seed] 考卷「{paper_title}」：得分 {result['total_score']}/{result['max_score']}"
                f"（{result['score_rate']:.0%}），正确 {result['correct_count']}/{result['question_count']}"
            )

        # 4) 汇总
        question_total = (
            db.query(Question).filter(Question.user_id == user.id).count()
        )
        entry_total = (
            db.query(KnowledgeEntry).filter(KnowledgeEntry.user_id == user.id).count()
        )
        print(
            f"[seed] 完成：{entry_total} 条知识库，{question_total} 道题目，"
            f"向量库 {get_vector_store().counts()}"
        )
    finally:
        db.close()


def ensure_entries() -> None:
    """补齐 KNOWLEDGE_ENTRIES 里尚未入库的资料（--ensure 专用）。

    用途：演示语料扩充后，不必重建整库（已有题目/考卷/错题本全部保留），
    只把缺的资料做分块与向量化。新补的资料不自动出题，需要时在界面上点「生成题目」。
    """
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == DEMO_USERNAME).first()
        if user is None:
            print("[ensure] 演示用户不存在，请先运行 python seed.py")
            return
        existing = {
            title
            for (title,) in db.query(KnowledgeEntry.title)
            .filter(KnowledgeEntry.user_id == user.id)
            .all()
        }
        added = 0
        for title, content in KNOWLEDGE_ENTRIES:
            if title in existing:
                continue
            entry = KnowledgeEntry(
                user_id=user.id,
                title=title,
                source_type="text",
                content=content,
                char_count=len(content),
                status="processing",
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            process_entry(db, entry)
            db.refresh(entry)
            print(f"[ensure] 补入「{title}」：{entry.chunk_count} 块，状态 {entry.status}")
            added += 1
        total = db.query(KnowledgeEntry).filter(KnowledgeEntry.user_id == user.id).count()
        print(f"[ensure] 完成：新增 {added} 条，现有 {total} 条资料")
    finally:
        db.close()


def ensure_builtin() -> None:
    """给已有用户补齐内置知识库与内置题库（--builtin 专用，幂等）。

    用途：内置语料/题库扩充后，不必重建整库，只补缺失的部分。
    内置题自动审核通过，可直接进入组卷池。
    """
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == DEMO_USERNAME).first()
        if user is None:
            print("[builtin] 演示用户不存在，请先运行 python seed.py")
            return
        from app.services.builtin import load_builtin

        stat = load_builtin(db, user.id)
        k, q, e = stat["knowledge"], stat["questions"], stat["eval_cases"]
        print(
            f"[builtin] 知识库 新增 {k['created']} / 跳过 {k['skipped']}；"
            f"题库 新增 {q['created']} / 跳过 {q['skipped']}"
            + (f"；未关联条目 {q['orphan']} 道" if q["orphan"] else "")
        )
        total_q = db.query(Question).filter(Question.user_id == user.id).count()
        builtin_q = (
            db.query(Question)
            .filter(Question.user_id == user.id, Question.source == "builtin")
            .count()
        )
        print(f"[builtin] 完成：题库共 {total_q} 道，其中内置 {builtin_q} 道")
        print(
            f"[builtin] 评测用例 新增 {e['created']} / 跳过 {e['skipped']}"
            + (f"；未匹配条目 {e['orphan']} 条" if e["orphan"] else "")
        )
    finally:
        db.close()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_all()
    if "--builtin" in sys.argv:
        # 只补内置内容（知识库语料 + 精选题库），不动已有数据
        ensure_builtin()
    elif "--ensure" in sys.argv:
        ensure_entries()
    else:
        seed()
