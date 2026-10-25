"""内置内容（知识库语料 + 精选题库）。

目标是「开箱即用」：不配置 LLM Key 也能拥有一套覆盖面完整、质量稳定的
知识库与题库，而不是让规则引擎临时生成术语填空题。

组织方式：按技术域 → 考点 → 题目 的知识图谱组织
- knowledge.py  内置知识库语料（domain / topic / title / content）
- questions_*.py 内置题库（按技术域分文件，题目通过 entry 标题关联到知识库条目）

题目字段约定：
    entry        关联的知识库条目标题（必须能在内置语料或已有条目中找到）
    q_type       choice | fill | judge
    difficulty   easy | medium | hard
    content      题干（填空题用 ______ 表示空位）
    options      选择题的 4 个选项（其余题型省略）
    answer       标准答案（选择题为 A/B/C/D，判断题为 正确/错误）
    explanation  解析
    keywords     关键词（用于检索与去重）
"""
