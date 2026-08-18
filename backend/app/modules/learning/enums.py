import enum


class TextProgressStatus(str, enum.Enum):
    UNSEEN = "UNSEEN"
    ACTIVE = "ACTIVE"
    WAITING_FOR_TEST_ASSIGNMENT = "WAITING_FOR_TEST_ASSIGNMENT"
    TEST_ASSIGNED = "TEST_ASSIGNED"
    MASTERED = "MASTERED"
    MANUALLY_ACQUIRED = "MANUALLY_ACQUIRED"
    DISABLED = "DISABLED"
    # Temporary, system-driven, fully reversible removal from rotation
    # caused by a CEFR tier rebalance (see rebalance_active_bank) — never
    # touches mastery_score/counts/next_review_at_exercise/rotation_position,
    # only status changes. Distinct from DISABLED (permanent, admin-only).
    BENCHED = "BENCHED"
