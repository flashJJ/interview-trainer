"""pytest 全局配置：测试前确保数据库表存在（与 lifespan 中的 init_db 一致）。"""

from app.database import init_db

init_db()
