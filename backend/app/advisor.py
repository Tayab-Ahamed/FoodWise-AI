"""Read-only conversation with constrained AI evidence curation, never agents/tools."""
from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import Field, field_validator

from . import advisor_evidence, db, station
from .schemas import StrictModel
from .errors import DomainError

router = APIRouter(prefix="/api/advisor", tags=["AI Kitchen Advisor"])


class ChatRequest(StrictModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[str] = Field(default_factory=list, max_length=8)
    planning_date: date | None = None
    meal: Literal["breakfast", "lunch", "dinner"] | None = None
    provider: Literal["offline", "groq", "gemini", "openrouter"] = "offline"
    share_aggregate_evidence: bool = False
    latitude: float = Field(default=13.086027, ge=-85, le=85)
    longitude: float = Field(default=77.641252, ge=-180, le=180)
    radius_km: int = Field(default=15, ge=1, le=30, strict=True)

    @field_validator("question")
    @classmethod
    def question_text(cls, value):
        if not value.strip():
            raise ValueError("Enter a question")
        return value.strip()

    @field_validator("history")
    @classmethod
    def history_limits(cls, value):
        if any(not q.strip() or len(q) > 1000 for q in value):
            raise ValueError("History must contain at most eight nonblank questions, each up to 1000 characters")
        return value


@router.get("/capabilities")
def capabilities():
    return {"suggestions": advisor_evidence.SUGGESTIONS, "providers": station.systems()["providers"],
            "today": str(advisor_evidence.today()), "timezone": "Asia/Kolkata",
            "read_only": True, "student_meal_pulse_available": False,
            "ai_role": "AI prioritizes server-authored evidence; facts, quantities and safety rules remain server-owned. No autonomous agents.",
            "privacy": "Your question and conversation stay local. Only recognized topic, public directory facts and aggregate evidence are shared when you explicitly enable AI. Staff names, review notes, record IDs and coordinates are excluded."}


@router.post("/chat")
def chat(request: ChatRequest):
    if request.provider != "offline" and not request.share_aggregate_evidence:
        raise DomainError("sharing_required", "Enable aggregate evidence sharing to use AI, or choose Offline.")
    cards, version, context = advisor_evidence.collect(request)
    # The canonical topic contains no raw question, personal data, staff notes or IDs.
    # Public directory text and calculated facts are the only model-visible cards.
    selected, status = (None, "offline")
    if request.provider != "offline":
        topic = ", ".join(context["topics"]) or "unsupported"
        aliases = {f"e{index}": c["id"] for index, c in enumerate(cards[:24])}
        public_cards = [{"id": alias, "title": lookup_card["title"], "text": lookup_card["text"]}
                        for alias, lookup_card in zip(aliases, cards[:24])]
        picked, status = station.provider_selection(request.provider, public_cards, topic)
        selected = [aliases[id] for id in picked] if picked else None
    lookup = {c["id"]: c for c in cards}
    # Critical facts cannot be dropped by a model's choice of evidence.
    required = [c["id"] for c in cards if c["id"] in {"plate_block", "untouched_review", "forecast_missing", "pulse_missing", "directory_scope", "acceptance_records", "waste_totals", "waste_trend", "portion_trial", "served_basis", "processing_records"}
                or c["id"].startswith(("forecast_", "inventory_"))]
    ids = list(dict.fromkeys([*(selected or [c["id"] for c in cards]), *required]))
    evidence = [lookup[id] for id in ids]
    mode = "ai_assisted" if selected else "offline"
    return {"mode": mode, "status": status, "provider": request.provider,
            "label": f"AI-assisted · {request.provider.title()}" if selected else "Offline · evidence-based response",
            "answer": "\n\n".join(c["text"] for c in evidence), "evidence": evidence,
            "dataset_version": version, "generated_at": db.now(), "context": context,
            "read_only": True, "suggestions": advisor_evidence.SUGGESTIONS,
            "limitations": ["AI prioritizes evidence; all displayed facts are authored and calculated by the backend.",
                            "Source labels are retained. Generated practice records are not measured kitchen operations.",
                            "This chat does not perform actions or establish food-safety certification."]}
