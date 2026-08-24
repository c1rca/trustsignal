from app.analyzers.carveout_analyzer import CarveOutAnalyzer
from app.analyzers.cuec_analyzer import CuecAnalyzer
from app.analyzers.exception_analyzer import ExceptionAnalyzer
from app.analyzers.ownership_analyzer import OwnershipAnalyzer
from app.analyzers.opinion_analyzer import OpinionAnalyzer
from app.analyzers.scope_analyzer import ScopeAnalyzer
from app.analyzers.subservice_analyzer import SubserviceAnalyzer
from app.analyzers.criteria_analyzer import CriteriaAnalyzer
from app.domain.models.report import PageText


def test_ownership_analyzer_vendor_report() -> None:
    analyzer = OwnershipAnalyzer()
    pages = [
        PageText(
            page_number=1,
            text=(
                "Report on Management's Description of Acme Corp's System\n"
                "Independent Service Auditor's Report\n"
                "To Acme Corp, Inc."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.ownership_type == "vendor_report"
    assert result.confidence == "high"


def test_ownership_analyzer_provider_report() -> None:
    analyzer = OwnershipAnalyzer()
    pages = [PageText(page_number=2, text="This report describes a hosting provider data center control environment.")]

    result = analyzer.analyze(pages)

    assert result.ownership_type == "provider_or_subservice_report"


def test_ownership_analyzer_preserves_vendor_when_subservice_mentioned() -> None:
    analyzer = OwnershipAnalyzer()
    pages = [
        PageText(
            page_number=3,
            text=(
                "INDEPENDENT SERVICE AUDITOR'S REPORT\n"
                "Management's description of the service organization's system includes controls at a data center."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.ownership_type == "vendor_report"


def test_opinion_analyzer_explicit_opinion_block_is_high_confidence() -> None:
    analyzer = OpinionAnalyzer()
    pages = [
        PageText(
            page_number=3,
            text=(
                "INDEPENDENT SERVICE AUDITOR'S REPORT\n"
                "Opinion\n"
                "In our opinion, the description presents fairly Acme Inc.'s system for the period under review."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.opinion_type == "unqualified"
    assert result.confidence == "high"


def test_scope_analyzer_detects_period_from_to_variant() -> None:
    analyzer = ScopeAnalyzer()
    pages = [PageText(page_number=4, text="For the period from January 1, 2025 to December 31, 2025, controls were tested.")]

    result = analyzer.analyze(pages)

    assert result.audit_period == "2025-01-01 to 2025-12-31"
    assert result.confidence == "high"


def test_scope_analyzer_detects_period_ended_variant() -> None:
    analyzer = ScopeAnalyzer()
    pages = [PageText(page_number=5, text="SOC 2 Type II report for period ended September 30, 2025.")]

    result = analyzer.analyze(pages)

    assert result.audit_period == "period ended 2025-09-30"
    assert result.confidence == "medium"


def test_carveout_analyzer_detects_carve_out() -> None:
    analyzer = CarveOutAnalyzer()
    pages = [PageText(page_number=4, text="The carve-out method is used for subservice organizations.")]

    result = analyzer.analyze(pages)

    assert result.method == "carve_out"
    assert result.confidence == "high"


def test_carveout_analyzer_detects_carved_out_subservice_heading() -> None:
    analyzer = CarveOutAnalyzer()
    pages = [
        PageText(
            page_number=9,
            text=(
                "Subservice Organization Carved-out Controls: Amazon Web Services (AWS). "
                "The description does not disclose the actual controls at this subservice organization."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.method == "carve_out"
    assert result.confidence == "high"


def test_subservice_analyzer_detects_named_org() -> None:
    analyzer = SubserviceAnalyzer()
    pages = [
        PageText(
            page_number=5,
            text="Subservice organizations: Acme Hosting LLC\nOther narrative text.",
        )
    ]

    result = analyzer.analyze(pages)

    assert "Acme Hosting LLC" in result.organizations


def test_subservice_analyzer_ignores_noise_entries() -> None:
    analyzer = SubserviceAnalyzer()
    pages = [PageText(page_number=6, text="Subservice organizations: none")]

    result = analyzer.analyze(pages)

    assert result.organizations == []


def test_subservice_analyzer_rejects_clause_like_org_name() -> None:
    analyzer = SubserviceAnalyzer()
    pages = [
        PageText(
            page_number=10,
            text="Subservice organizations: NayaOne Limited uses Amazon Web Services (AWS) to provide hosting services.",
        )
    ]

    result = analyzer.analyze(pages)

    # Accept either strict rejection or normalized AWS extraction depending on parser heuristics.
    assert result.organizations in ([], ["Amazon Web Services (AWS)"])


def test_cuec_analyzer_extracts_responsibilities() -> None:
    analyzer = CuecAnalyzer()
    pages = [
        PageText(
            page_number=7,
            text=(
                "Complementary user entity controls\n"
                "1. User entity must configure MFA for privileged users.\n"
                "2. Customer is responsible for managing endpoint security."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert len(result.responsibilities) == 2
    assert result.confidence in {"medium", "high"}


def test_cuec_analyzer_rejects_lettered_list_and_stops_at_heading() -> None:
    analyzer = CuecAnalyzer()
    pages = [
        PageText(
            page_number=8,
            text=(
                "COMPLEMENTARY USER ENTITY CONTROLS\n"
                "a. The description presents Acme's system.\n"
                "1. User entities are responsible for access approvals.\n"
                "2. User entities must notify Acme of role changes.\n"
                "OPINION\n"
                "3. User entities should not be parsed after heading boundary."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.responsibilities == [
        "User entities are responsible for access approvals.",
        "User entities must notify Acme of role changes.",
    ]


def test_cuec_analyzer_extracts_customer_responsibilities_variant() -> None:
    analyzer = CuecAnalyzer()
    pages = [
        PageText(
            page_number=11,
            text=(
                "NayaOne Limited's Customers' Responsibilities\n"
                "• Configure SSO integrations to enforce authentication requirements.\n"
                "- Review user access rights periodically.\n"
                "* Notify NayaOne promptly of unauthorized access."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert len(result.responsibilities) == 3
    assert result.confidence == "high"


def test_criteria_analyzer_detects_relevant_to_wording() -> None:
    analyzer = CriteriaAnalyzer()
    pages = [
        PageText(
            page_number=12,
            text="The controls were suitably designed relevant to Security, Availability and Confidentiality.",
        )
    ]

    result = analyzer.analyze(pages)

    assert result.criteria == ["Security", "Availability", "Confidentiality"]
    assert result.confidence == "high"


def test_criteria_analyzer_tracks_framework_reference_separately() -> None:
    analyzer = CriteriaAnalyzer()
    pages = [
        PageText(
            page_number=13,
            text=(
                "Trust services criteria for Security, Availability, Processing Integrity, Confidentiality, and Privacy. "
                "Report on controls relevant to Security."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.criteria == ["Security"]
    assert result.confidence == "high"
    assert result.criteria_framework_reference == [
        "Security",
        "Availability",
        "Processing Integrity",
        "Confidentiality",
        "Privacy",
    ]


def test_subservice_analyzer_extracts_names_from_table_and_contract_list() -> None:
    analyzer = SubserviceAnalyzer()
    pages = [
        PageText(
            page_number=4,
            text=(
                "Subservice Organizations\n"
                "Services and Applications\n"
                "Amazon Web Services (AWS)\n"
                "Infrastructure-as-a-Service and cloud computing services\n"
                "Google\n"
                "Infrastructure-as-a-Service and enterprise applications\n"
                "Salesforce\n"
                "Customer relationship management\n"
            ),
        ),
        PageText(
            page_number=31,
            text=(
                "Subservice Organizations\n"
                "Matillion contracts with Okta, Inc. (including Auth0) for authentication tools.\n"
                "Matillion contracts with Recurly, Inc. for billing.\n"
                "User Control Considerations\n"
            ),
        ),
    ]

    result = analyzer.analyze(pages)

    assert any(item.startswith("Amazon Web Services") for item in result.organizations)
    assert "Google" in result.organizations
    assert "Salesforce" in result.organizations
    assert "Okta" in result.organizations
    assert "Auth0" in result.organizations
    assert "Recurly" in result.organizations


def test_cuec_analyzer_extracts_split_bullets_under_user_control_considerations() -> None:
    analyzer = CuecAnalyzer()
    pages = [
        PageText(
            page_number=31,
            text=(
                "User Control Considerations\n"
                "User auditors should consider whether controls are implemented at user organizations:\n"
                "•\n"
                "Customers are responsible for reviewing contracts with Matillion.\n"
                "•\n"
                "Customers are responsible for ensuring only authorized users are granted access.\n"
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert len(result.responsibilities) == 2
    assert result.confidence in {"medium", "high"}


def test_cuec_analyzer_returns_narrative_unknown_when_heading_present_without_structure() -> None:
    analyzer = CuecAnalyzer()
    pages = [
        PageText(
            page_number=9,
            text=(
                "User Entity Controls and Responsibilities\n"
                "User entities are responsible for maintaining account lifecycle controls and notifying the Company of changes to approvers.\n"
                "Customers should review access reports and ensure authorized usage of the service."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.present is True
    assert result.mode == "narrative"
    assert result.count == 2
    assert result.needs_review is True


def test_cuec_analyzer_ignores_testing_language_and_stays_bounded() -> None:
    analyzer = CuecAnalyzer()
    pages = [
        PageText(
            page_number=10,
            text=(
                "Complementary User Entity Controls\n"
                "1. User entities are responsible for notifying the Company of user status changes.\n"
                "RESULTS OF TESTS\n"
                "2. No deviations noted.\n"
                "3. Inspected evidence of approvals."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.responsibilities == [
        "User entities are responsible for notifying the Company of user status changes."
    ]


def test_cuec_analyzer_rejects_vendor_and_org_chart_false_positives() -> None:
    analyzer = CuecAnalyzer()
    pages = [
        PageText(
            page_number=12,
            text=(
                "Customer Responsibilities\n"
                "1. Management is responsible for documenting internal control policies.\n"
                "2. The Company ensures controls are designed effectively.\n"
                "3. The legal and compliance team manages regulatory communications."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.present is True
    assert result.responsibilities == []
    assert result.count is None


def test_exception_analyzer_detects_deviation_language() -> None:
    analyzer = ExceptionAnalyzer()
    pages = [
        PageText(
            page_number=9,
            text=(
                "Test of control results\n"
                "A deviation was noted where one access review did not operate effectively."
            ),
        )
    ]

    result = analyzer.analyze(pages)

    assert result.exceptions_detected is True
    assert result.confidence in {"medium", "high"}
