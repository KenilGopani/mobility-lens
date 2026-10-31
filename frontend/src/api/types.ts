import type { Geometry, FeatureCollection } from 'geojson';

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
export interface RunRef {
  id: string;
  status: string;
  pipeline_version: string;
  started_at: string;
  completed_at: string | null;
}
export interface Area {
  id: string;
  name: string;
  slug: string;
  source: string;
  score: number | null;
  confidence: number | null;
  rank: number | null;
  analysis_run_id: string | null;
  last_run_at: string | null;
}
export interface Model {
  id: string | null;
  name: string;
  version: string | null;
  weights: Record<string, number>;
}
export interface ScoringModel extends Model {
  id: string;
  is_default: boolean;
  normalization_version: string;
}
export interface Component {
  metric: string;
  display_name: string | null;
  raw_value: number | null;
  normalized_value: number | null;
  weight: number;
  effective_weight: number;
  contribution: number | null;
  confidence: number | null;
}
export interface Highlight {
  metric: string;
  display_name: string | null;
  raw_value: number | null;
  normalized_value: number;
  unit: string | null;
}
export interface Counts {
  info: number;
  warning: number;
  critical: number;
}
export interface AreaScore {
  service_area_id: string;
  name: string;
  slug: string;
  score: number | null;
  confidence: number | null;
  rank: number | null;
  components: Component[];
  strengths: Highlight[];
  risks: Highlight[];
  warnings: string[];
  run: RunRef | null;
}
export interface Summary extends Omit<AreaScore, 'service_area_id'> {
  id: string;
  scoring_model: Model | null;
  ranked_areas: number;
  finding_counts: Counts;
}
export interface Comparison {
  scoring_model: Model;
  areas: AreaScore[];
}
export interface Preview extends Comparison {
  temporary: true;
}
export interface Detail {
  id: string;
  name: string;
  source: string;
  boundary: Geometry;
  bbox: [number, number, number, number];
}
export interface Metric {
  key: string;
  display_name: string;
  description: string;
  unit: string;
  higher_is_better: boolean;
  normalization_method: string;
  ref_min: number | null;
  ref_max: number | null;
  version: string;
  raw_value: number | null;
  normalized_value: number | null;
  confidence: number | null;
}
export interface Metrics {
  service_area_id: string;
  run: RunRef;
  analyzed_at: string | null;
  source: Record<string, unknown>;
  metrics: Metric[];
}
export interface Quality {
  service_area_id: string;
  run: RunRef;
  analyzed_at: string | null;
  source: Record<string, unknown>;
  finding_counts: Counts;
  findings: {
    rule_key: string;
    severity: 'info' | 'warning' | 'critical';
    message: string;
    affected_fraction: number | null;
  }[];
  completeness: {
    cells_count: number;
    low_confidence_threshold: number;
    low_confidence_cells: number;
    low_confidence_share: number | null;
    metrics: { metric: string; null_cells: number; null_share: number | null }[];
  };
}
export interface CellProperties {
  h3_index: string;
  raw_value: number | null;
  normalized_value: number | null;
  confidence: number | null;
  overlap_ratio: number;
  score: number | null;
}
export interface Cells extends FeatureCollection<Geometry, CellProperties> {
  metric: string;
  analysis_run_id: string;
  limit: number;
  truncated: boolean;
}
