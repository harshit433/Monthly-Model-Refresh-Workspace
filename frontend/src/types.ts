export interface Weight {
  kind: "scalar" | "vector" | "rule";
  value?: number | number[];
  breakpoint?: string;
  side?: string;
}

export interface Target {
  var: string;
  region: string;
  percent: number;
  weight: Weight;
  series?: number[] | null;
  active?: boolean;
}

export interface SourceRef {
  var: string;
  region: string;
}

export interface Proposal {
  sources: SourceRef[];
  source_var: string;
  source_region: string;
  category: string;
  action: string;
  kind: string | null;
  targets: Target[];
  confidence: number;
  provenance: string;
  status: string;
  evidence?: Record<string, unknown>;
  breakpoint?: string;
}

export interface Recon {
  var: string;
  region: string;
  transformed_total: number;
  processed_total: number;
  pct_diff: number;
  aligned: boolean;
}

export interface Analysis {
  reconciliation: Recon[];
  weekly_deviation: { dates: string[]; values: number[]; weeks_within_tol: number; weeks_total: number };
  unaligned: { mismatch: Array<{ var: string; region: string; pct_diff: number }>; raw_only: SourceRef[]; processed_only: SourceRef[] };
}

export interface DomainCounts {
  total: number;
  by_status: Record<string, number>;
  by_provenance: Record<string, number>;
}

export interface Summary {
  id: string;
  env: string;
  bmc: string;
  refresh: string;
  dates: string[];
  domains: Record<string, DomainCounts>;
  analysis: Analysis;
}

export interface Insights {
  total: number;
  scope: string;
  by_variable: Array<{ var: string; region: string; contribution: number; pct: number; roi?: number; invest?: number }>;
  by_region: Array<{ region: string; contribution: number; pct: number }>;
  trend: { dates: string[]; values: number[] };
}

export interface ExtendResult {
  historical_weeks: number;
  new_weeks: number;
  combined_weeks: number;
  new_dates: string[];
  overlap: string[];
  new_contribution_total: number;
}
