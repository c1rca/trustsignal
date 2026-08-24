from app.analyzers.opinion_analyzer import OpinionAnalyzer
from app.domain.models.report import PageText


def test_except_for_without_opinion_context_does_not_trigger_qualified() -> None:
    analyzer = OpinionAnalyzer()
    pages = [
        PageText(
            page_number=12,
            text=(
                "User role definitions include full read/write access except for administration. "
                "No opinion language is present on this page."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.opinion_type != "qualified"
