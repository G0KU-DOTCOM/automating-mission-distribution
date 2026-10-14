"""Approval of an exact local proposal; this never authorizes external delivery."""

from datetime import datetime, timezone

from .models import DemoDataError
from .source_data import digest


class StaleProposalError(DemoDataError):
    """The proposal changed after the browser displayed it."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def review_revision(task: dict, public: dict) -> str:
    # Approval and view-only additions must not change the version being approved.
    proposal = {key: value for key, value in task.items()
                if key not in {"approval", "events", "public_opportunity", "competition_ref"}}
    return digest({"proposal": proposal, "public": public})


def advance_review_version(task: dict) -> None:
    # Prevent an old form becoming valid again when a person is changed A -> B -> A.
    task["review_version"] = task.get("review_version", 0) + 1


def approval_current(task: dict, public: dict) -> bool:
    approval = task.get("approval", {})
    return (approval.get("state") == "godkjent" and task["lifecycle"] == "aktiv"
            and approval.get("review_revision") == review_revision(task, public))


def approval_blocker(task: dict, public: dict) -> str | None:
    if task["lifecycle"] != "aktiv":
        return "En avlyst oppgave kan ikke godkjennes."
    if public["conflicts"]:
        return "Kildene har motstridende opplysninger. Konflikten må avklares før godkjenning."
    if public["possible_duplicate_ids"]:
        return "Mulig duplikat må avklares før godkjenning."
    if not public.get("classification", {}).get("should_route", True):
        return "Den siste fagvurderingen gir ingen relevante treff. Relevansen må avklares først."
    if task["owner"] is None:
        return "Velg en mottaker før du godkjenner forslaget."
    return None


def invalidate_approval(task: dict, public: dict, reason: str) -> bool:
    if task.get("approval", {}).get("state") != "godkjent" or approval_current(task, public):
        return False
    task["approval"].update(state="utdatert", invalidated_at=now_utc(), invalidated_reason=reason)
    return True
