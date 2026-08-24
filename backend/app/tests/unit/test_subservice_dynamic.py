from app.analyzers.subservice_analyzer import SubserviceAnalyzer
from app.domain.models.report import PageText


def test_extracts_site_four_from_bullet_row() -> None:
    analyzer = SubserviceAnalyzer()
    pages = [
        PageText(page_number=1, text="D. Subservice Organizations\n• Site-Four, LLC - Data center hosting")
    ]
    result = analyzer.analyze(pages)
    assert "Site-Four, LLC" in result.organizations


def test_extracts_aliases_from_contract_list() -> None:
    analyzer = SubserviceAnalyzer()
    pages = [
        PageText(
            page_number=2,
            text=(
                "Subservice organizations: contracts with Amazon Web Services (AWS), Google, and Heroku for hosting services."
            ),
        )
    ]
    result = analyzer.analyze(pages)
    assert "Amazon Web Services (AWS)" in result.organizations
    assert "Google" in result.organizations
    assert "Heroku" in result.organizations
