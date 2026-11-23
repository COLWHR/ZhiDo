import request from '@/utils/request'

export interface DecisionLog {
  id: number | null
  scope: string | null
  reference_id: number | null
  label: string | null
  confidence: number | null
  layer: string | null
  keyword: string | null
  elapsed_ms: number | null
  text: string | null
  created_at: string | null
}

export interface DecisionEvaluation {
  val_size?: number
  model?: { accuracy: number; macro_f1: number }
  rule_baseline?: { accuracy: number; macro_f1: number }
  ml_avg_ms_per_request?: number
}

export interface DecisionOverview {
  dataset: {
    model_available: boolean
    model_path: string
    dataset_csv: string
  }
  evaluation: DecisionEvaluation
  logs: DecisionLog[]
}

const noCache = { headers: { 'Cache-Control': 'no-cache' } }

export const decisionApi = {
  overview: () =>
    request.get('/decision/overview', noCache).then((r) => r.data as DecisionOverview),
}
