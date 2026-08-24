from app.analyzers.criteria_analyzer import CriteriaAnalyzer
from app.domain.models.report import PageText


def test_framework_reference_with_scope_markers_keeps_framework_separate() -> None:
    analyzer = CriteriaAnalyzer()
    pages = [
        PageText(
            page_number=4,
            text=(
                "Independent Service Auditor's Report.\n"
                "Report on controls relevant to security and availability.\n"
                "Trust Services Criteria for Security, Availability, Processing Integrity, Confidentiality, and Privacy."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert set(result.criteria) == {"Security", "Availability"}
    assert result.criteria_framework_reference
    assert result.confidence == "high"
