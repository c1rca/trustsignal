class ReportValidationError(ValueError):
    """Raised when uploaded report fails validation."""


class ReportNotFoundError(KeyError):
    """Raised when a report is not found."""
