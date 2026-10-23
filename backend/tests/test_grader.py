"""评分器单测：客观题精确匹配与填空题分档。"""

from types import SimpleNamespace

import pytest

from app.services.grader import (
    Grader,
    extract_choice_letter,
    normalize_judge_answer,
)
from app.services.runtime import get_embeddings


def make_question(q_type, answer, content="题干"):
    return SimpleNamespace(
        q_type=q_type,
        answer=answer,
        content=content,
        explanation="解析",
    )


@pytest.fixture(scope="module")
def grader():
    return Grader(embeddings=get_embeddings())


class TestNormalizers:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("A", "A"), ("a. 选项", "A"), ("  B ", "B"), ("选项C", "C"), ("D、", "D"),
        ],
    )
    def test_extract_choice_letter(self, raw, expected):
        assert extract_choice_letter(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("正确", True), ("对", True), ("√", True), ("true", True), ("是", True),
            ("错误", False), ("错", False), ("×", False), ("false", False), ("不对", False),
            ("", None), ("也许", None),
        ],
    )
    def test_normalize_judge_answer(self, raw, expected):
        assert normalize_judge_answer(raw) is expected


class TestChoiceGrading:
    def test_correct(self, grader):
        result = grader.grade(make_question("choice", "B"), "B")
        assert result.score == 10.0 and result.is_correct

    def test_wrong(self, grader):
        result = grader.grade(make_question("choice", "B"), "A")
        assert result.score == 0.0 and not result.is_correct
        assert "B" in result.feedback

    def test_empty(self, grader):
        result = grader.grade(make_question("choice", "B"), "")
        assert result.score == 0.0 and "未作答" in result.feedback


class TestJudgeGrading:
    def test_correct_variants(self, grader):
        assert grader.grade(make_question("judge", "正确"), "对").is_correct
        assert grader.grade(make_question("judge", "错误"), "×").is_correct

    def test_wrong(self, grader):
        assert not grader.grade(make_question("judge", "正确"), "错误").is_correct


class TestFillGrading:
    def test_exact_match(self, grader):
        result = grader.grade(make_question("fill", "布隆过滤器"), "布隆过滤器")
        assert result.score == 10.0 and result.is_correct

    def test_alternatives_slash(self, grader):
        result = grader.grade(make_question("fill", "互斥锁 / 分布式锁"), "分布式锁")
        assert result.is_correct

    def test_containment(self, grader):
        result = grader.grade(make_question("fill", "布隆过滤器"), "使用布隆过滤器来解决")
        assert result.is_correct

    def test_partial_semantic(self, grader):
        # 「布隆过滤机制」不含完整术语，但语义接近（相似度约 0.63）=> 半分
        result = grader.grade(make_question("fill", "布隆过滤器"), "布隆过滤机制")
        assert result.score == 5.0 and not result.is_correct

    def test_wrong(self, grader):
        result = grader.grade(make_question("fill", "布隆过滤器"), "缓存空值")
        assert result.score == 0.0

    def test_empty(self, grader):
        result = grader.grade(make_question("fill", "布隆过滤器"), "  ")
        assert result.score == 0.0 and "未作答" in result.feedback
