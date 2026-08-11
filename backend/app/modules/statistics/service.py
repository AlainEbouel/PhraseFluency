import uuid
from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.modules.evaluations.enums import Verdict
from app.modules.evaluations.models import Attempt, Evaluation
from app.modules.learning.engine import DEFAULT_ACTIVE_BANK_SIZE
from app.modules.learning.enums import TextProgressStatus
from app.modules.learning.models import UserTextProgress
from app.modules.tests.models import Test, TestAttempt, TestAttemptStatus
from app.modules.tests.service import list_tests_for_user
from app.modules.texts.models import Pattern, Text, TextVersion, pattern_text_versions
from app.shared.mixins import utcnow
from app.shared.models import AIUsage

SUCCESS_VERDICTS = (
    Verdict.CORRECT_NATURAL,
    Verdict.CORRECT_UNNATURAL,
    Verdict.CORRECT_WITH_WRITING_ISSUES,
)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _trend(db: Session, user_id: uuid.UUID, since=None) -> dict:
    query = (
        select(Evaluation.verdict, func.count())
        .join(Attempt, Attempt.active_evaluation_id == Evaluation.id)
        .where(Attempt.user_id == user_id)
        .group_by(Evaluation.verdict)
    )
    if since is not None:
        query = query.where(Attempt.created_at >= since)

    rows = db.execute(query).all()
    total = sum(count for _, count in rows)
    natural = sum(count for verdict, count in rows if verdict == Verdict.CORRECT_NATURAL)
    success = sum(count for verdict, count in rows if verdict in SUCCESS_VERDICTS)
    return {
        "attempts_count": total,
        "natural_rate": _rate(natural, total),
        "success_rate": _rate(success, total),
    }


def get_dashboard(db: Session, user_id: uuid.UUID) -> dict:
    status_rows = db.execute(
        select(UserTextProgress.status, func.count())
        .where(UserTextProgress.user_id == user_id)
        .group_by(UserTextProgress.status)
    ).all()
    status_counts = {status.value: count for status, count in status_rows}

    test_rows = list_tests_for_user(db, user_id)
    tests_available = sum(1 for _, latest, _ in test_rows if latest is None)
    tests_in_progress = sum(
        1
        for _, latest, _ in test_rows
        if latest is not None and latest.status == TestAttemptStatus.IN_PROGRESS
    )
    tests_completed = sum(
        1
        for _, latest, _ in test_rows
        if latest is not None and latest.status == TestAttemptStatus.COMPLETED
    )

    all_time = _trend(db, user_id)
    recent = _trend(db, user_id, since=utcnow() - timedelta(days=7))

    return {
        "mastered_count": status_counts.get(TextProgressStatus.MASTERED.value, 0),
        "active_count": status_counts.get(TextProgressStatus.ACTIVE.value, 0),
        "active_target": DEFAULT_ACTIVE_BANK_SIZE,
        "waiting_for_test_count": status_counts.get(
            TextProgressStatus.WAITING_FOR_TEST_ASSIGNMENT.value, 0
        ),
        "tests_available": tests_available,
        "tests_in_progress": tests_in_progress,
        "tests_completed": tests_completed,
        "natural_answer_rate": all_time["natural_rate"],
        "overall_success_rate": all_time["success_rate"],
        "recent_trend": recent,
    }


def get_detailed_statistics(db: Session, user_id: uuid.UUID) -> dict:
    status_rows = db.execute(
        select(UserTextProgress.status, func.count())
        .where(UserTextProgress.user_id == user_id)
        .group_by(UserTextProgress.status)
    ).all()
    status_counts = [{"status": s.value, "count": c} for s, c in status_rows]

    verdict_rows = db.execute(
        select(Evaluation.verdict, func.count())
        .join(Attempt, Attempt.active_evaluation_id == Evaluation.id)
        .where(Attempt.user_id == user_id)
        .group_by(Evaluation.verdict)
    ).all()
    verdict_counts = [{"verdict": v.value, "count": c} for v, c in verdict_rows]

    trend_7d = _trend(db, user_id, since=utcnow() - timedelta(days=7))
    trend_30d = _trend(db, user_id, since=utcnow() - timedelta(days=30))
    trend_all_time = _trend(db, user_id)

    hardest_rows = db.execute(
        select(
            UserTextProgress.text_id,
            TextVersion.french_text,
            UserTextProgress.incorrect_count,
            UserTextProgress.times_presented,
        )
        .join(Text, Text.id == UserTextProgress.text_id)
        .join(TextVersion, TextVersion.id == Text.current_version_id)
        .where(UserTextProgress.user_id == user_id, UserTextProgress.incorrect_count > 0)
        .order_by(UserTextProgress.incorrect_count.desc())
        .limit(10)
    ).all()
    hardest_texts = [
        {
            "text_id": text_id,
            "french_text": french_text,
            "incorrect_count": incorrect_count,
            "times_presented": times_presented,
        }
        for text_id, french_text, incorrect_count, times_presented in hardest_rows
    ]

    avg_attempts = db.scalar(
        select(func.avg(UserTextProgress.times_presented)).where(
            UserTextProgress.user_id == user_id,
            UserTextProgress.status == TextProgressStatus.MASTERED,
        )
    )

    hint_total, presented_total = db.execute(
        select(
            func.coalesce(func.sum(UserTextProgress.hint_count), 0),
            func.coalesce(func.sum(UserTextProgress.times_presented), 0),
        ).where(UserTextProgress.user_id == user_id)
    ).one()
    hint_usage_rate = _rate(hint_total, presented_total)

    writing_issue_count = (
        db.scalar(
            select(func.coalesce(func.sum(UserTextProgress.writing_issue_count), 0)).where(
                UserTextProgress.user_id == user_id
            )
        )
        or 0
    )

    input_rows = db.execute(
        select(Attempt.input_method, func.count())
        .where(Attempt.user_id == user_id)
        .group_by(Attempt.input_method)
    ).all()
    input_method_counts = [{"input_method": m.value, "count": c} for m, c in input_rows]

    reeval_attempt_ids = db.execute(
        select(Evaluation.attempt_id)
        .join(Attempt, Attempt.id == Evaluation.attempt_id)
        .where(Attempt.user_id == user_id)
        .group_by(Evaluation.attempt_id)
        .having(func.count() > 1)
    ).scalars().all()
    verdict_changed_count = 0
    for attempt_id in reeval_attempt_ids:
        evals = db.scalars(
            select(Evaluation)
            .where(Evaluation.attempt_id == attempt_id)
            .order_by(Evaluation.evaluation_number)
        ).all()
        if evals[0].verdict != evals[-1].verdict:
            verdict_changed_count += 1

    error_category_rows = db.execute(
        select(func.unnest(Evaluation.error_categories).label("category"), func.count())
        .join(Attempt, Attempt.active_evaluation_id == Evaluation.id)
        .where(Attempt.user_id == user_id)
        .group_by("category")
    ).all()
    error_category_counts = [{"category": category, "count": c} for category, c in error_category_rows]

    natural_case = case((Evaluation.verdict == Verdict.CORRECT_NATURAL, 1), else_=0)
    success_case = case((Evaluation.verdict.in_(SUCCESS_VERDICTS), 1), else_=0)

    difficulty_rows = db.execute(
        select(
            TextVersion.difficulty,
            func.count(),
            func.sum(natural_case),
            func.sum(success_case),
        )
        .join(Attempt, Attempt.active_evaluation_id == Evaluation.id)
        .join(TextVersion, TextVersion.id == Attempt.text_version_id)
        .where(Attempt.user_id == user_id)
        .group_by(TextVersion.difficulty)
    ).all()
    performance_by_difficulty = [
        {
            "difficulty": difficulty.value,
            "attempts_count": total,
            "natural_rate": _rate(natural, total),
            "success_rate": _rate(success, total),
        }
        for difficulty, total, natural, success in difficulty_rows
    ]

    context_rows = db.execute(
        select(
            func.unnest(TextVersion.contexts).label("context"),
            func.count(),
            func.sum(natural_case),
            func.sum(success_case),
        )
        .join(Attempt, Attempt.active_evaluation_id == Evaluation.id)
        .join(TextVersion, TextVersion.id == Attempt.text_version_id)
        .where(Attempt.user_id == user_id)
        .group_by("context")
    ).all()
    performance_by_context = [
        {
            "context": context,
            "attempts_count": total,
            "natural_rate": _rate(natural, total),
            "success_rate": _rate(success, total),
        }
        for context, total, natural, success in context_rows
    ]

    patterns_encountered_count = (
        db.scalar(
            select(func.count(func.distinct(Pattern.id)))
            .join(
                pattern_text_versions, pattern_text_versions.c.pattern_id == Pattern.id
            )
            .join(
                Attempt,
                Attempt.text_version_id == pattern_text_versions.c.text_version_id,
            )
            .where(Attempt.user_id == user_id)
        )
        or 0
    )

    test_attempt_rows = db.execute(
        select(
            TestAttempt.status,
            TestAttempt.correct_count,
            TestAttempt.incorrect_count,
            TestAttempt.attempt_number,
        )
        .join(Test, Test.id == TestAttempt.test_id)
        .where(Test.user_id == user_id)
    ).all()
    tests_completed = sum(
        1 for status, *_ in test_attempt_rows if status == TestAttemptStatus.COMPLETED
    )
    total_correct = sum(correct for _, correct, _, _ in test_attempt_rows)
    total_incorrect = sum(incorrect for _, _, incorrect, _ in test_attempt_rows)
    retakes_count = sum(1 for *_, attempt_number in test_attempt_rows if attempt_number > 1)

    ai_usage_rows = db.execute(
        select(
            AIUsage.operation,
            func.count(),
            func.coalesce(func.sum(AIUsage.input_tokens), 0),
            func.coalesce(func.sum(AIUsage.output_tokens), 0),
            func.coalesce(func.sum(AIUsage.estimated_cost), 0),
        )
        .where(AIUsage.user_id == user_id)
        .group_by(AIUsage.operation)
    ).all()
    ai_usage = [
        {
            "operation": operation.value,
            "count": count,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "estimated_cost": float(estimated_cost),
        }
        for operation, count, input_tokens, output_tokens, estimated_cost in ai_usage_rows
    ]

    return {
        "status_counts": status_counts,
        "verdict_counts": verdict_counts,
        "trend_7d": trend_7d,
        "trend_30d": trend_30d,
        "trend_all_time": trend_all_time,
        "hardest_texts": hardest_texts,
        "avg_attempts_before_mastery": float(avg_attempts) if avg_attempts is not None else None,
        "hint_usage_rate": hint_usage_rate,
        "writing_issue_count": int(writing_issue_count),
        "input_method_counts": input_method_counts,
        "reevaluation": {
            "total_reevaluated": len(reeval_attempt_ids),
            "verdict_changed_count": verdict_changed_count,
        },
        "error_category_counts": error_category_counts,
        "performance_by_difficulty": performance_by_difficulty,
        "performance_by_context": performance_by_context,
        "patterns_encountered_count": patterns_encountered_count,
        "test_performance": {
            "tests_completed": tests_completed,
            "total_correct": total_correct,
            "total_incorrect": total_incorrect,
            "retakes_count": retakes_count,
        },
        "ai_usage": ai_usage,
    }
