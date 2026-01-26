from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.constants import (
    DraftEventType,
    DraftStatus,
    normalize_event_type,
    normalize_status,
)
from app.models.draft import Draft
from app.models.draft_event import DraftEvent


def transition_draft_status(
    db: Session,
    draft: Draft,
    to_status: str,
    event_type: str,
    metadata: dict | None = None,
    commit: bool = True,
) -> Draft:
    from_status = normalize_status(draft.status)
    to_status = normalize_status(to_status)
    event_type = normalize_event_type(event_type)

    metadata = dict(metadata) if metadata else {}
    if event_type == DraftEventType.START_RECOGNIZE:
        if to_status != DraftStatus.RECOGNIZING:
            metadata["normalized"] = True
            metadata["original_to_status"] = to_status
            to_status = DraftStatus.RECOGNIZING
    elif event_type == DraftEventType.RECOGNIZE_SUCCESS:
        if to_status != DraftStatus.DRAFT_READY:
            metadata["normalized"] = True
            metadata["original_to_status"] = to_status
            to_status = DraftStatus.DRAFT_READY
    elif event_type == DraftEventType.RECOGNIZE_FAIL:
        if to_status != DraftStatus.FAILED:
            metadata["normalized"] = True
            metadata["original_to_status"] = to_status
            to_status = DraftStatus.FAILED

    draft_event = DraftEvent(
        draft_id=draft.id,
        from_status=from_status,
        to_status=to_status,
        event_type=event_type,
        metadata_=metadata or None,
    )

    draft.status = to_status
    draft.updated_at = datetime.now(timezone.utc)

    db.add(draft_event)
    db.add(draft)
    if commit:
        db.commit()
        db.refresh(draft)
    else:
        db.flush()
    return draft


def create_draft_event(
    db: Session,
    draft_id: int,
    from_status: str | None,
    to_status: str,
    event_type: str,
    metadata: dict | None,
    commit: bool = True,
) -> DraftEvent:
    draft_event = DraftEvent(
        draft_id=draft_id,
        from_status=from_status,
        to_status=to_status,
        event_type=event_type,
        metadata_=metadata,
    )

    db.add(draft_event)
    if commit:
        db.commit()
        db.refresh(draft_event)
    else:
        db.flush()
    return draft_event
