"""Signal classifier for work intelligence data.

Categorizes raw work signals (opportunities, emails, chats, commits) into
8 actionable signal types. Designed as a deterministic rule-based classifier
with optional LLM enhancement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SignalType(str, Enum):
    WINS = "wins"
    LOSSES = "losses"
    ESCALATIONS = "escalations"
    COMPETE = "compete"
    PRODUCTS = "products"
    IP = "ip"
    PEOPLE = "people"
    OTHERS = "others"


@dataclass
class Signal:
    """A classified work signal."""

    type: SignalType
    source: str
    summary: str
    confidence: float  # 0.0 to 1.0
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "source": self.source,
            "summary": self.summary,
            "confidence": self.confidence,
        }


@dataclass
class SignalReport:
    """Aggregated signal classification report."""

    signals: list[Signal] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_signals": len(self.signals),
            "by_type": self.summary,
            "signals": [s.to_dict() for s in self.signals],
        }


# ── Keyword patterns for rule-based classification ──

_PATTERNS: dict[SignalType, list[str]] = {
    SignalType.WINS: [
        "closed won", "deal signed", "contract executed", "deployment complete",
        "go-live", "successful", "approved", "accepted",
    ],
    SignalType.LOSSES: [
        "closed lost", "lost to", "churned", "cancelled", "declined",
        "chose competitor", "went with",
    ],
    SignalType.ESCALATIONS: [
        "escalat", "blocked", "urgent", "critical", "sev1", "sev2",
        "management attention", "at risk", "delayed",
    ],
    SignalType.COMPETE: [
        "aws", "gcp", "google cloud", "databricks", "snowflake",
        "competitor", "competitive", "bedrock", "sagemaker", "vertex",
    ],
    SignalType.PRODUCTS: [
        "feature request", "product feedback", "roadmap", "gap",
        "capability", "limitation", "improvement",
    ],
    SignalType.IP: [
        "open source", "patent", "reference architecture", "published",
        "blog post", "whitepaper", "presentation", "demo",
    ],
    SignalType.PEOPLE: [
        "hired", "promoted", "onboarded", "left the team",
        "collaboration", "mentoring", "training",
    ],
}


def classify_opportunity(opp: dict) -> Signal:
    """Classify a single CRM opportunity record."""
    status = opp.get("status", "").lower()
    notes = opp.get("notes", "").lower()
    name = opp.get("name", "")
    account = opp.get("account", "Unknown")

    if status == "won":
        return Signal(
            type=SignalType.WINS,
            source=f"CRM:{account}",
            summary=f"Won: {name} (${opp.get('estimated_value', 0):,.0f})",
            confidence=0.95,
            raw_data=opp,
        )

    if status == "lost":
        summary = f"Lost: {name}"
        # Check for compete signals in notes
        for keyword in _PATTERNS[SignalType.COMPETE]:
            if keyword in notes:
                return Signal(
                    type=SignalType.COMPETE,
                    source=f"CRM:{account}",
                    summary=f"{summary} — competitive loss ({keyword})",
                    confidence=0.85,
                    raw_data=opp,
                )
        return Signal(
            type=SignalType.LOSSES,
            source=f"CRM:{account}",
            summary=summary,
            confidence=0.90,
            raw_data=opp,
        )

    # Open opportunities — classify by notes content
    for signal_type, keywords in _PATTERNS.items():
        for keyword in keywords:
            if keyword in notes:
                return Signal(
                    type=signal_type,
                    source=f"CRM:{account}",
                    summary=f"{name}: {keyword} signal detected",
                    confidence=0.70,
                    raw_data=opp,
                )

    return Signal(
        type=SignalType.OTHERS,
        source=f"CRM:{account}",
        summary=f"Active: {name} — {opp.get('stage', 'Unknown')} stage",
        confidence=0.50,
        raw_data=opp,
    )


def classify_text_signals(text: str, source: str = "text") -> list[Signal]:
    """Classify free-text content (emails, chats, transcripts) into signals."""
    signals = []
    text_lower = text.lower()

    for signal_type, keywords in _PATTERNS.items():
        for keyword in keywords:
            if keyword in text_lower:
                # Find the sentence containing the keyword for context
                sentences = text.split(".")
                context = next(
                    (s.strip() for s in sentences if keyword in s.lower()),
                    keyword,
                )
                signals.append(Signal(
                    type=signal_type,
                    source=source,
                    summary=context[:200],
                    confidence=0.65,
                ))

    if not signals:
        signals.append(Signal(
            type=SignalType.OTHERS,
            source=source,
            summary=text[:200],
            confidence=0.30,
        ))

    return signals


def build_signal_report(
    opportunities: list[dict] | None = None,
    texts: list[dict[str, str]] | None = None,
) -> SignalReport:
    """Build a complete signal report from opportunities and free-text sources."""
    all_signals: list[Signal] = []

    if opportunities:
        for opp in opportunities:
            all_signals.append(classify_opportunity(opp))

    if texts:
        for item in texts:
            text = item.get("text", "")
            source = item.get("source", "text")
            all_signals.extend(classify_text_signals(text, source))

    # Build summary counts
    summary = {}
    for st in SignalType:
        count = sum(1 for s in all_signals if s.type == st)
        if count > 0:
            summary[st.value] = count

    return SignalReport(signals=all_signals, summary=summary)
