"""测试共享夹具：内存数据库 + 检索语料。

只用内存库，绝不触碰 data/interview_trainer.db（见 test_settings.py 的事故记录）。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.services import text_utils as int_utils


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


CORPUS = {
    "Python 并发": [
        "Python 的 GIL 是全局解释器锁，它保证同一时刻只有一个线程执行字节码。"
        "因此 CPU 密集型任务用多线程无法获得并行加速，应该改用多进程。",
        "多进程通过 multiprocessing 模块创建独立解释器进程，每个进程有独立的 GIL，"
        "适合 CPU 密集场景；进程间通信需要借助队列或共享内存。",
        "asyncio 使用事件循环实现单线程并发，适合 IO 密集场景。"
        "协程在遇到 await 时让出控制权，由事件循环调度其他任务。",
    ],
    "MySQL 索引": [
        "B+ 树是 MySQL InnoDB 的默认索引结构，非叶子节点只存键，叶子节点存数据并用链表相连，"
        "因此范围查询效率很高。",
        "聚簇索引的叶子节点直接存放整行数据，二级索引叶子节点存放主键值，"
        "所以二级索引查询需要回表。",
        "最左前缀原则要求联合索引的查询条件从最左列开始连续匹配，否则索引失效。",
    ],
}


@pytest.fixture()
def seeded(db_session):
    """建一个用户 + 两篇资料 + 6 个知识块，返回 (user, chunk_ids)。"""
    user = models.User(username="tester", password_hash="x")
    db_session.add(user)
    db_session.flush()

    chunk_ids: list[int] = []
    for title, contents in CORPUS.items():
        entry = models.KnowledgeEntry(
            user_id=user.id, title=title, content="\n".join(contents), status="ready"
        )
        db_session.add(entry)
        db_session.flush()
        for seq, content in enumerate(contents):
            chunk = models.KnowledgeChunk(
                entry_id=entry.id, seq=seq, content=content, char_count=len(content)
            )
            db_session.add(chunk)
            db_session.flush()
            chunk.vector_id = f"chunk_{chunk.id}"
            chunk_ids.append(chunk.id)
    db_session.commit()
    return user, chunk_ids


# ---------------------------------------------------------------- 检索假后端
class FakeEmbeddings:
    """用内置 n-gram 向量代替真实 Embedding API。"""

    mode = "local"

    def embed(self, text: str):
        return int_utils.embed_text(text)

    def embed_batch(self, texts):
        return [int_utils.embed_text(t) for t in texts]


class FakeStore:
    """把语料存内存里做暴力余弦检索，模拟向量库行为。"""

    def __init__(self, corpus):
        self.corpus = corpus

    def search_chunks(self, embedding, top_k=5, entry_ids=None):
        scored = []
        for doc in self.corpus:
            if entry_ids and doc["entry_id"] not in entry_ids:
                continue
            sim = int_utils.cosine(embedding, int_utils.embed_text(doc["content"]))
            scored.append((sim, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "vector_id": f"chunk_{doc['chunk_id']}",
                "content": doc["content"],
                "entry_id": doc["entry_id"],
                "seq": doc["seq"],
                "score": round(sim, 4),
            }
            for sim, doc in scored[:top_k]
        ]


def patch_retrieval(monkeypatch, db, user_id):
    """把检索服务的 embedding/向量库换成假实现（测试检索与评测共用）。"""
    from app.services import retrieval

    corpus = retrieval.load_corpus(db, user_id)
    retrieval.invalidate_index()
    monkeypatch.setattr(retrieval, "get_embeddings", lambda: FakeEmbeddings())
    monkeypatch.setattr(retrieval, "get_vector_store", lambda: FakeStore(corpus))
