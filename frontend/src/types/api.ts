export type UploadReportResponse = {
  report_id: string
  filename: string
  page_count: number
  uploaded_at: string
}

export type ReportMetadataResponse = {
  report_id: string
  filename: string
  page_count: number
  uploaded_at: string
}

export type FindingStatus = 'pass' | 'fail' | 'needs_review'

export type Finding = {
  key: 'opinion' | 'scope' | 'criteria' | 'ownership' | 'carveout' | 'exceptions'
  status: FindingStatus
  summary: string
  page_number: number
  confidence: 'low' | 'medium' | 'high'
  review_required: boolean
  review_reason: string
}

export type EvidenceItem = {
  finding_key: string
  page_number: number
  quote: string
  rationale: string
}

export type AuthConfigResponse = {
  require_login: boolean
  setup_required: boolean
}

export type AnalysisJobStatusResponse = {
  status: 'not_started' | 'running' | 'done' | 'failed'
  message?: string | null
}

export type AnalysisProgressResponse = {
  status: 'idle' | 'running' | 'done' | 'error'
  stage: string
  message: string
  ocr_active: boolean
  ocr_current_page: number | null
  ocr_total_pages: number | null
  ocr_pages_remaining: number | null
}

export type AnalysisResponse = {
  report_metadata: {
    report_id: string
    filename: string
    page_count: number
    uploaded_at: string
  }
  executive_snapshot: {
    opinion: string
    audit_period: string
    criteria_covered: string[]
    ownership: string
  }
  findings: Finding[]
  evidence_index: EvidenceItem[]
  evidence_by_finding: Record<string, EvidenceItem[]>
  review_summary: {
    total_findings: number
    review_required_count: number
    review_required_keys: string[]
    status_counts: {
      pass: number
      fail: number
      needs_review: number
    }
  }
  reviewer_takeaway: string
  ownership: {
    ownership_type: string
    summary: string
    confidence: 'low' | 'medium' | 'high'
  }
  subservices: {
    organizations: string[]
    confidence: 'low' | 'medium' | 'high'
  }
  carveout: {
    method: string
    confidence: 'low' | 'medium' | 'high'
  }
  cuecs: {
    responsibilities: string[]
    confidence: 'low' | 'medium' | 'high'
    present: boolean
    mode: string
    count: number | null
    needs_review: boolean
  }
  exceptions: {
    exceptions_detected: boolean
    confidence: 'low' | 'medium' | 'high'
  }
}
