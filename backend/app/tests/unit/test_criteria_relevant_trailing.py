from app.analyzers.criteria_analyzer import CriteriaAnalyzer
from app.domain.models.report import PageText


def test_controls_relevant_to_without_terminal_punctuation() -> None:
    analyzer = CriteriaAnalyzer()
    pages = [
        PageText(
            page_number=1,
            text=(
                "INDEPENDENT SERVICE AUDITOR'S REPORT ON CONTROLS RELEVANT TO SECURITY, CONFIDENTIALITY & AVAILABILITY "
                "July 24, 2024 through July 23, 2025"
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert set(result.criteria) == {"Security", "Confidentiality", "Availability"}
