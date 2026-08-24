import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react'

import {
  getAnalysisJobStatus,
  getAnalysisProgress,
  getReportAnalysis,
  purgeReports,
  reportFileUrlWithAuth,
  startAnalysisJob,
  uploadReport,
} from '../../lib/api'
import type { AnalysisProgressResponse, AnalysisResponse, FindingStatus, UploadReportResponse } from '../../types/api'

function statusBadgeClass(status: FindingStatus, key: string): string {
  if (key === 'opinion') {
    if (status === 'pass') return 'bg-emerald-100 text-emerald-800 border-emerald-200'
    return 'bg-red-100 text-red-800 border-red-200'
  }

  if (status === 'needs_review') return 'bg-amber-100 text-amber-800 border-amber-200'
  if (status === 'pass') return 'bg-slate-100 text-slate-700 border-slate-200'
  return 'bg-slate-100 text-slate-600 border-slate-200'
}

function statusBadgeLabel(status: FindingStatus, key: string): string {
  if (key === 'opinion') {
    if (status === 'pass') return 'unqualified'
    if (status === 'fail') return 'modified'
    return 'unclear'
  }

  if (status === 'pass') return ''
  if (status === 'needs_review') return 'needs review'
  return 'not found'
}

function reportFileUrl(reportId: string, page?: number): string {
  return reportFileUrlWithAuth(reportId, page)
}

function findingLabel(key: string): string {
  if (key === 'cuecs') return 'CEUCs'
  return key
}

type QueueFilter = 'all' | 'needs_review'

export function UploadDropzone() {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [showLongRunningIndicator, setShowLongRunningIndicator] = useState(false)
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgressResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<UploadReportResponse | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [queueFilter, setQueueFilter] = useState<QueueFilter>('all')
  const [showAllEvidence, setShowAllEvidence] = useState(false)
  const [viewerPage, setViewerPage] = useState<number | undefined>(undefined)

  useEffect(() => {
    const handleBeforeUnload = () => {
      void purgeReports()
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])

  useEffect(() => {
    if (!isUploading && !isAnalyzing) {
      setElapsedSeconds(0)
      setShowLongRunningIndicator(false)
      return
    }

    const timer = window.setInterval(() => {
      setElapsedSeconds((s) => s + 1)
    }, 1000)

    const delayedIndicator = window.setTimeout(() => {
      setShowLongRunningIndicator(true)
    }, 4000)

    return () => {
      window.clearInterval(timer)
      window.clearTimeout(delayedIndicator)
    }
  }, [isUploading, isAnalyzing])

  useEffect(() => {
    if (!isAnalyzing || !result?.report_id) return

    let cancelled = false

    const poll = async () => {
      try {
        const progress = await getAnalysisProgress(result.report_id)
        if (!cancelled) {
          setAnalysisProgress(progress)
        }
      } catch {
        // best effort progress
      }
    }

    void poll()
    const interval = window.setInterval(() => {
      void poll()
    }, 1000)

    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [isAnalyzing, result?.report_id])

  useEffect(() => {
    // Always start at default PDF view on new analysis load;
    // only jump pages on explicit user click.
    setViewerPage(undefined)
  }, [analysis?.report_metadata.report_id])

  const onPickFile = () => fileInputRef.current?.click()

  const onDragOver = (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    if (!isUploading && !isAnalyzing) setIsDragging(true)
  }

  const onDragLeave = (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    if (!event.currentTarget.contains(event.relatedTarget as Node)) {
      setIsDragging(false)
    }
  }

  const onDrop = async (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    setIsDragging(false)
    if (isUploading || isAnalyzing) return

    const file = event.dataTransfer.files?.[0]
    if (!file) return

    await handleSelectedFile(file)
  }

  const handleSelectedFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a PDF file.')
      return
    }

    try {
      setError(null)
      setAnalysis(null)
      setResult(null)
      setViewerPage(undefined)
      setQueueFilter('all')
      setShowAllEvidence(false)
      setAnalysisProgress(null)

      setIsUploading(true)
      const payload = await uploadReport(file)
      setResult(payload)
      setIsUploading(false)

      setIsAnalyzing(true)
      await startAnalysisJob(payload.report_id)

      for (;;) {
        const status = await getAnalysisJobStatus(payload.report_id)
        if (status.status === 'done') {
          break
        }
        if (status.status === 'failed') {
          throw new Error(status.message ?? 'Analysis failed')
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
      }

      const analysisPayload = await getReportAnalysis(payload.report_id)
      setAnalysis(analysisPayload)
      setAnalysisProgress({
        status: 'done',
        stage: 'complete',
        message: 'Analysis complete',
        ocr_active: false,
        ocr_current_page: null,
        ocr_total_pages: null,
        ocr_pages_remaining: null,
      })
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Upload failed')
      setResult(null)
      setAnalysis(null)
      setAnalysisProgress({
        status: 'error',
        stage: 'error',
        message: 'Analysis failed',
        ocr_active: false,
        ocr_current_page: null,
        ocr_total_pages: null,
        ocr_pages_remaining: null,
      })
    } finally {
      setIsUploading(false)
      setIsAnalyzing(false)
    }
  }

  const onFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    await handleSelectedFile(file)
    event.target.value = ''
  }

  const openEvidencePage = (page?: number) => {
    if (!page || page <= 0) return
    setViewerPage(page)
  }

  const visibleFindings = useMemo(() => {
    if (!analysis) return []
    if (queueFilter === 'all') return analysis.findings
    return analysis.findings.filter((f) => f.review_required)
  }, [analysis, queueFilter])


  const reportId = analysis?.report_metadata.report_id ?? result?.report_id
  const viewerSrc = reportId ? reportFileUrl(reportId, viewerPage ?? 1) : null

  const cuecEvidencePage =
    analysis?.evidence_by_finding.cuecs?.find((entry) => entry.page_number && entry.page_number > 0)?.page_number ??
    analysis?.evidence_index.find((entry) => entry.finding_key === 'cuecs' && entry.page_number > 0)?.page_number

  return (
    <section
      className={`rounded-2xl border border-dashed bg-panel p-8 shadow-soft transition-colors ${
        isDragging ? 'border-accent bg-blue-50/40' : 'border-slate-300'
      }`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <div className="mx-auto flex w-full max-w-[1800px] flex-col gap-6">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-ink">SOC 2 Reviewer Workspace</h2>
          <p className="mt-1 text-sm text-muted">Upload a report to review findings with synchronized evidence navigation.</p>
        </div>

        <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={onFileChange}
          />

          <button
            type="button"
            className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isUploading || isAnalyzing}
            onClick={onPickFile}
          >
            {isUploading ? 'Uploading…' : isAnalyzing ? 'Analyzing…' : 'Analyze Report'}
          </button>

          <p className="text-xs text-muted">Accepted type: .pdf • Max size: 25 MB</p>

          {showLongRunningIndicator && (isUploading || isAnalyzing) && (
            <div className="w-full rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
              <div>
                <span className="font-medium">{isUploading ? 'Uploading…' : 'Analyzing…'}</span> Elapsed: {elapsedSeconds}s
              </div>
              {isAnalyzing && analysisProgress ? (
                <div className="mt-1 text-xs text-blue-800">
                  {analysisProgress.ocr_active
                    ? `OCR in progress: page ${analysisProgress.ocr_current_page ?? '?'} of ${analysisProgress.ocr_total_pages ?? '?'} (${analysisProgress.ocr_pages_remaining ?? '?'} remaining)`
                    : analysisProgress.message}
                </div>
              ) : null}
            </div>
          )}

          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          {result ? (
            <div className="w-full rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-left text-sm text-emerald-900">
              <p className="font-medium">Upload complete</p>
              <p>
                <a
                  href={reportFileUrl(result.report_id)}
                  target="_blank"
                  rel="noreferrer"
                  className="text-emerald-900 hover:underline"
                >
                  {result.filename}
                </a>{' '}
                • {result.page_count} page{result.page_count === 1 ? '' : 's'}
              </p>
            </div>
          ) : null}
        </div>

        {analysis && viewerSrc ? (
          <div className="grid gap-4 lg:grid-cols-[0.8fr_1.4fr]">
            <section className="space-y-4">
              <div className="rounded-lg border border-border bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-ink">Review Queue</p>
                  <div className="flex gap-2 text-xs">
                    <button
                      type="button"
                      onClick={() => setQueueFilter('all')}
                      className={`rounded-md border px-2 py-1 ${queueFilter === 'all' ? 'border-accent text-accent' : 'border-slate-300 text-slate-600'}`}
                    >
                      All
                    </button>
                    <button
                      type="button"
                      onClick={() => setQueueFilter('needs_review')}
                      className={`rounded-md border px-2 py-1 ${queueFilter === 'needs_review' ? 'border-accent text-accent' : 'border-slate-300 text-slate-600'}`}
                    >
                      Needs Review
                    </button>
                  </div>
                </div>

                <p className="mt-2 text-xs text-slate-500">
                  {analysis.review_summary.review_required_count} of {analysis.review_summary.total_findings} items need review.
                </p>
              </div>

              {(queueFilter === 'all' || visibleFindings.length > 0) && (
                <div className="rounded-lg border border-border bg-white p-4">
                  <p className="text-sm font-semibold text-ink">Deterministic Findings</p>
                  <ul className="mt-3 space-y-2">
                    {visibleFindings.map((finding) => {
                      const fallbackPage =
                        finding.page_number > 0
                          ? finding.page_number
                          : analysis.evidence_by_finding[finding.key]?.find((e) => e.page_number > 0)?.page_number
                      return (
                        <li
                          key={finding.key}
                          className={`rounded-md border border-slate-200 p-3 ${fallbackPage ? 'cursor-pointer hover:bg-slate-50' : ''}`}
                          onClick={() => {
                            if (fallbackPage) openEvidencePage(fallbackPage)
                          }}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-sm font-medium capitalize text-ink">{findingLabel(finding.key)}</p>
                            {(() => {
                              const label =
                                finding.key === 'opinion'
                                  ? (analysis.opinion.opinion_type || statusBadgeLabel(finding.status, finding.key))
                                  : statusBadgeLabel(finding.status, finding.key)
                              return label ? (
                                <span
                                  className={`rounded-full border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${statusBadgeClass(finding.status, finding.key)}`}
                                >
                                  {label}
                                </span>
                              ) : null
                            })()}
                          </div>

                          <p className="mt-1 text-sm text-slate-700">{finding.summary}</p>

                          {finding.key === 'cuecs' && analysis.cuecs.responsibilities.length > 2 ? (
                            <>
                              <p className="mt-2 text-sm text-slate-700">Extracted: {analysis.cuecs.responsibilities.length}</p>
                              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                                {analysis.cuecs.responsibilities.map((item, idx) => (
                                  <li key={`cuec-inline-${idx}`} className="break-words">{item}</li>
                                ))}
                              </ul>
                            </>
                          ) : null}

                          <p className="mt-1 text-xs text-slate-500">
                            Confidence: {finding.confidence} {finding.review_required ? '• Review required' : '• No review flag'}
                          </p>

                          {finding.review_required && finding.review_reason ? (
                            <p className="mt-1 text-xs text-amber-700">Reason: {finding.review_reason}</p>
                          ) : null}

                          <p className="mt-2 text-xs text-slate-500">
                            {fallbackPage ? `Evidence page: ${fallbackPage}` : 'Evidence page: n/a'}
                          </p>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )}

              <div className="rounded-lg border border-border bg-white p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-ink">Evidence by Finding</p>
                  <button
                    type="button"
                    onClick={() => setShowAllEvidence((v) => !v)}
                    className="text-xs font-medium text-accent hover:underline"
                  >
                    {showAllEvidence ? 'Hide all' : 'Show all'}
                  </button>
                </div>

                {showAllEvidence ? (
                  <div className="mt-3 space-y-3">
                    {Object.entries(analysis.evidence_by_finding).map(([findingKey, items]) => (
                      <div key={findingKey} className="rounded-md border border-slate-200 p-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">{findingKey}</p>
                        <ul className="mt-2 space-y-2">
                          {items.map((item, idx) => (
                            <li key={`${findingKey}-${idx}`} className="rounded border border-slate-100 bg-slate-50 p-2">
                              <p className="text-xs text-slate-600">
                                page {item.page_number || 'n/a'}
                                {item.page_number ? (
                                  <>
                                    {' '}
                                    •{' '}
                                    <button
                                      type="button"
                                      onClick={() => openEvidencePage(item.page_number)}
                                      className="font-medium text-accent hover:underline"
                                    >
                                      Open page
                                    </button>
                                  </>
                                ) : null}
                              </p>
                              <p className="mt-1 break-words text-sm text-slate-800">“{item.quote}”</p>
                              <p className="mt-1 text-xs text-slate-500">{item.rationale}</p>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">Hidden by default to keep review focused.</p>
                )}
              </div>
            </section>

            <section className="space-y-4">
              <div className="rounded-lg border border-border bg-white p-4">
                <p className="text-sm font-semibold text-ink">Executive Snapshot</p>
                <ul className="mt-2 space-y-1 text-sm text-slate-700">
                  <li>
                    <span className="font-medium text-ink">Opinion:</span> {analysis.executive_snapshot.opinion}
                  </li>
                  <li>
                    <span className="font-medium text-ink">Audit period:</span> {analysis.executive_snapshot.audit_period}
                  </li>
                  <li>
                    <span className="font-medium text-ink">Criteria:</span>{' '}
                    {analysis.executive_snapshot.criteria_covered.length
                      ? analysis.executive_snapshot.criteria_covered.join(', ')
                      : 'None detected'}
                  </li>
                </ul>
              </div>

              <div className="rounded-lg border border-border bg-white p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold text-ink">Source PDF</p>
                </div>
                <iframe title="Source PDF" src={viewerSrc} className="h-[72vh] w-full" />
              </div>
            </section>
          </div>
        ) : null}
      </div>
    </section>
  )
}
