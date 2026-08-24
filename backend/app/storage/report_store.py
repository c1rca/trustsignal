from datetime import UTC, datetime, timedelta

from app.domain.models.report import SocReport
from app.schemas.analysis_models import AnalysisResponse


class ReportStore:
    def __init__(self, ttl_minutes: int = 15) -> None:
        self._reports: dict[str, dict[str, SocReport]] = {}
        self._analyses: dict[str, dict[str, AnalysisResponse]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    def save(self, report: SocReport) -> None:
        owner_reports = self._reports.setdefault(report.owner_id, {})
        owner_analyses = self._analyses.setdefault(report.owner_id, {})
        # Single-active-report privacy mode per authenticated session.
        owner_reports.clear()
        owner_analyses.clear()
        owner_reports[report.id] = report

    def get(self, owner_id: str, report_id: str) -> SocReport | None:
        self.purge_expired()
        return self._reports.get(owner_id, {}).get(report_id)

    def save_analysis(self, owner_id: str, report_id: str, analysis: AnalysisResponse) -> None:
        self.purge_expired()
        owner_analyses = self._analyses.setdefault(owner_id, {})
        owner_analyses[report_id] = analysis

    def get_analysis(self, owner_id: str, report_id: str) -> AnalysisResponse | None:
        self.purge_expired()
        return self._analyses.get(owner_id, {}).get(report_id)

    def purge_all(self, owner_id: str) -> None:
        self._reports.pop(owner_id, None)
        self._analyses.pop(owner_id, None)

    def purge_expired(self) -> None:
        now = datetime.now(UTC)
        expired_owners: list[str] = []

        for owner_id, owner_reports in list(self._reports.items()):
            expired_report_ids = [
                report_id
                for report_id, report in owner_reports.items()
                if now - report.uploaded_at > self._ttl
            ]
            for report_id in expired_report_ids:
                owner_reports.pop(report_id, None)
                self._analyses.get(owner_id, {}).pop(report_id, None)

            if not owner_reports:
                expired_owners.append(owner_id)

        for owner_id in expired_owners:
            self._reports.pop(owner_id, None)
            self._analyses.pop(owner_id, None)
