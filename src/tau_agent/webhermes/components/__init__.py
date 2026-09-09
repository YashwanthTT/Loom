"""Phase 3: component library (manual locators first, no AI)."""

from tau_agent.webhermes.components.base import (
    BrowserComponent,
    VerificationResult,
    VerificationSpec,
)
from tau_agent.webhermes.components.library import (
    Click,
    Download,
    Extract,
    Fill,
    Navigate,
    Search,
    Select,
    Wait,
)

__all__ = [
    "BrowserComponent",
    "Click",
    "Download",
    "Extract",
    "Fill",
    "Navigate",
    "Search",
    "Select",
    "VerificationResult",
    "VerificationSpec",
    "Wait",
]
