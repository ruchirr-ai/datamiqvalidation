/**
 * PDF Report — Types & Color System
 * Base color: #00ADEF (sky blue)
 */
import jsPDF from 'jspdf';
import type {
  AssessmentFullReport,
  RecommendationsData,
  TCOData
} from '../../services/assessmentsApi';

export interface QueryInsightsSummary {
  total_query_count: number;
  active_users_count: number;
  avg_execution_time_seconds: number;
  total_bytes_scanned: number;
  total_bytes_billed: number;
  total_slot_milliseconds: number;
  cache_hit_rate: number;
  cache_hits: number;
  cache_misses: number;
  read_queries: number;
  write_queries: number;
  max_concurrent_queries: number;
  avg_concurrent_queries: number;
  max_slot_milliseconds: number;
  min_slot_milliseconds: number;
  avg_slot_ms_per_query: number;
  max_query_runtime_seconds: number;
  min_query_runtime_seconds: number;
  avg_query_runtime_seconds: number;
  peak_slot_utilization: number;
  avg_slot_utilization: number;
}

export interface QueryInsightsQuery {
  job_id: string;
  execution_time: string | null;
  query_text: string;
  bytes_scanned: number;
  slot_milliseconds: number;
  slot_utilization: number;
  est_runtime_seconds: number;
  cache_hit: boolean;
  user_email: string;
}

export interface QueryInsightsData {
  summary: QueryInsightsSummary;
  queries: QueryInsightsQuery[];
}

export interface PDFGeneratorOptions {
  report: AssessmentFullReport;
  selectedSections: string[];
  assessmentId: number;
  recommendations?: RecommendationsData | null;
  tcoData?: TCOData | null;
  queryInsightsData?: QueryInsightsData | null;
}

export interface PDFContext {
  doc: jsPDF;
  y: number;
  margin: number;
  pageW: number;
  pageH: number;
  contentW: number;
}

// ── #00ADEF sky blue palette ──
export const C = {
  // Primary — #00ADEF and shades
  PRIMARY:      [0, 173, 239]    as const,  // #00ADEF
  PRIMARY_D:    [0, 139, 197]    as const,  // Darker
  PRIMARY_L:    [77, 199, 244]   as const,  // Lighter
  PRIMARY_XL:   [179, 229, 249]  as const,  // Very light
  PRIMARY_BG:   [232, 247, 253]  as const,  // Lightest bg

  // Accent — indigo
  ACCENT:       [79, 70, 229]    as const,
  ACCENT_L:     [238, 242, 255]  as const,

  // Neutrals
  DARK:         [15, 23, 42]     as const,
  DARK2:        [51, 65, 85]     as const,
  GRAY:         [100, 116, 139]  as const,
  GRAY_L:       [148, 163, 184]  as const,
  GRAY_XL:      [226, 232, 240]  as const,
  GRAY_BG:      [248, 250, 252]  as const,
  WHITE:        [255, 255, 255]  as const,

  // Semantic
  SUCCESS:      [16, 185, 129]   as const,
  SUCCESS_BG:   [236, 253, 245]  as const,
  WARNING:      [245, 158, 11]   as const,
  WARNING_BG:   [255, 251, 235]  as const,
  DANGER:       [239, 68, 68]    as const,
  DANGER_BG:    [254, 242, 242]  as const,
  PURPLE:       [139, 92, 246]   as const,
  PURPLE_BG:    [245, 243, 255]  as const,
  BLUE:         [0, 173, 239]    as const,  // Same as PRIMARY
  BLUE_BG:      [232, 247, 253]  as const,

  // Table
  TH_BG:        [232, 247, 253]  as const,
  TH_TEXT:      [0, 139, 197]    as const,
  BORDER:       [226, 232, 240]  as const,
  ALT_ROW:      [248, 250, 252]  as const,
  BODY_TEXT:    [51, 65, 85]     as const,
};
