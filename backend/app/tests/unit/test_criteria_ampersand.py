from app.analyzers.criteria_analyzer import CriteriaAnalyzer
from app.domain.models.report import PageText


def test_relevant_to_with_ampersand_and_order_variation() -> None:
    analyzer = CriteriaAnalyzer()
    pages = [
        PageText(
            page_number=1,
            text="INDEPENDENT SERVICE AUDITOR'S REPORT ON CONTROLS RELEVANT TO SECURITY, CONFIDENTIALITY & AVAILABILITY",
        )
    ]

    result = analyzer.analyze(pages)

    assert set(result.criteria) == {"Security", "Confidentiality", "Availability"}
    assert result.confidence in {"high", "medium"}
