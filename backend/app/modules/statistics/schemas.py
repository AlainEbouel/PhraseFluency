import uuid

from pydantic import BaseModel


class TrendOut(BaseModel):
    attempts_count: int
    natural_rate: float
    success_rate: float


class DashboardOut(BaseModel):
    mastered_count: int
    active_count: int
    active_target: int
    waiting_for_test_count: int
    tests_available: int
    tests_in_progress: int
    tests_completed: int
    natural_answer_rate: float
    overall_success_rate: float
    recent_trend: TrendOut


class StatusCountOut(BaseModel):
    status: str
    count: int


class VerdictCountOut(BaseModel):
    verdict: str
    count: int


class HardestTextOut(BaseModel):
    text_id: uuid.UUID
    french_text: str
    incorrect_count: int
    times_presented: int


class InputMethodCountOut(BaseModel):
    input_method: str
    count: int


class ReevaluationStatsOut(BaseModel):
    total_reevaluated: int
    verdict_changed_count: int


class ErrorCategoryCountOut(BaseModel):
    category: str
    count: int


class DifficultyPerformanceOut(BaseModel):
    difficulty: str
    attempts_count: int
    natural_rate: float
    success_rate: float


class ContextPerformanceOut(BaseModel):
    context: str
    attempts_count: int
    natural_rate: float
    success_rate: float


class TestPerformanceOut(BaseModel):
    tests_completed: int
    total_correct: int
    total_incorrect: int
    retakes_count: int


class AIUsageSummaryOut(BaseModel):
    operation: str
    count: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float


class WeaknessCategoryOut(BaseModel):
    category: str
    count: int


class WeaknessSuggestionOut(BaseModel):
    category: str
    explanation: str
    suggestion: str


class WeaknessProfileOut(BaseModel):
    has_enough_data: bool
    weaknesses: list[WeaknessCategoryOut]
    suggestions: list[WeaknessSuggestionOut]


class DetailedStatisticsOut(BaseModel):
    status_counts: list[StatusCountOut]
    verdict_counts: list[VerdictCountOut]
    trend_7d: TrendOut
    trend_30d: TrendOut
    trend_all_time: TrendOut
    hardest_texts: list[HardestTextOut]
    avg_attempts_before_mastery: float | None
    hint_usage_rate: float
    writing_issue_count: int
    input_method_counts: list[InputMethodCountOut]
    reevaluation: ReevaluationStatsOut
    error_category_counts: list[ErrorCategoryCountOut]
    performance_by_difficulty: list[DifficultyPerformanceOut]
    performance_by_context: list[ContextPerformanceOut]
    patterns_encountered_count: int
    test_performance: TestPerformanceOut
    ai_usage: list[AIUsageSummaryOut]
