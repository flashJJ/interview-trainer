"""演示数据种子脚本。

用法：
    python seed.py            # 写入演示数据（幂等，已存在 demo 用户则跳过）
    python seed.py --reset    # 清空数据库与向量库后重新播种

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
    (
        "Python 装饰器与上下文管理器",
        """装饰器本质上是一个接收函数作为参数并返回新函数的可调用对象，利用闭包在不修改原函数代码的前提下增强函数行为，常用于日志、计时、权限校验和结果缓存。

@ 语法糖等价于 func = decorator(func)。带参数的装饰器需要三层嵌套：最外层接收装饰器参数，中间层接收被装饰函数，最内层实现包装逻辑。functools.wraps 用于保留原函数的名称和文档字符串等元信息，避免调试困难。

类装饰器和 functools.lru_cache 是标准库中的常见实践，lru_cache 自动缓存函数返回值，适合加速纯函数的重复计算。

上下文管理器通过 with 语句在进入和退出时自动执行准备与清理动作，保证资源正确释放。实现方式有两种：定义 __enter__ 和 __exit__ 方法的类，或者用 contextlib.contextmanager 装饰生成器，yield 之前是进入逻辑，之后是退出逻辑。

__exit__ 方法接收异常类型、异常值和追踪信息，返回 True 可以抑制异常。contextlib.suppress 可以简洁地忽略指定类型的异常。

常见陷阱：装饰器内直接返回内层函数导致引用丢失；多个装饰器叠加时执行顺序是从下往上包装；闭包中循环变量的延迟绑定问题。""",
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
    """清空关系库与向量库（--reset 专用）。"""
    with engine.begin() as conn:
        for table in _TABLES:
            conn.execute(text(f"DELETE FROM {table}"))
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
                        db, user.id, outcome.drafts, get_embeddings(), get_vector_store()
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


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_all()
    seed()
