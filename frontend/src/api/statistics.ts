import { apiRequest } from "./client";

export interface Trend {
  attempts_count: number;
  natural_rate: number;
  success_rate: number;
}

export interface Dashboard {
  mastered_count: number;
  active_count: number;
  active_target: number;
  waiting_for_test_count: number;
  tests_available: number;
  tests_in_progress: number;
  tests_completed: number;
  natural_answer_rate: number;
  overall_success_rate: number;
  recent_trend: Trend;
}

export interface DetailedStatistics {
  status_counts: { status: string; count: number }[];
  verdict_counts: { verdict: string; count: number }[];
  trend_7d: Trend;
  trend_30d: Trend;
  trend_all_time: Trend;
  hardest_texts: { text_id: string; french_text: string; incorrect_count: number; times_presented: number }[];
  avg_attempts_before_mastery: number | null;
  hint_usage_rate: number;
  writing_issue_count: number;
  input_method_counts: { input_method: string; count: number }[];
  reevaluation: { total_reevaluated: number; verdict_changed_count: number };
  error_category_counts: { category: string; count: number }[];
  performance_by_difficulty: { difficulty: string; attempts_count: number; natural_rate: number; success_rate: number }[];
  performance_by_context: { context: string; attempts_count: number; natural_rate: number; success_rate: number }[];
  patterns_encountered_count: number;
  test_performance: { tests_completed: number; total_correct: number; total_incorrect: number; retakes_count: number };
  ai_usage: { operation: string; count: number; input_tokens: number; output_tokens: number; estimated_cost: number }[];
}

export interface WeaknessProfile {
  has_enough_data: boolean;
  weaknesses: { category: string; count: number }[];
  suggestions: { category: string; explanation: string; suggestion: string }[];
}

export function fetchDashboard(): Promise<Dashboard> {
  return apiRequest("/api/v1/statistics/dashboard");
}

export function fetchDetailedStatistics(): Promise<DetailedStatistics> {
  return apiRequest("/api/v1/statistics/detailed");
}

export function fetchWeaknessProfile(): Promise<WeaknessProfile> {
  return apiRequest("/api/v1/statistics/weakness-profile");
}
