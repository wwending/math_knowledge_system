import uuid

from app.core.constants import DraftEventType, DraftStatus
from app.core.security import utcnow
from app.db.migrations import upgrade_database
from app.db.session import SessionLocal, engine
from app.models.draft import Draft
from app.models.draft_event import DraftEvent
from app.models.source_asset import SourceAsset
from app.models.user import User
from app.services.draft_state import create_draft_event, transition_draft_status


def main() -> None:
    upgrade_database(str(engine.url))

    db = SessionLocal()
    try:
        phone = f"188{uuid.uuid4().int % 10**8:08d}"
        user = User(
            username=phone,
            phone=phone,
            display_name="Smoke Test",
            email=None,
            hashed_password="not_secure",
            role="user",
            status="active",
            must_change_password=False,
            password_changed_at=utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        source_asset = SourceAsset(
            user_id=user.id,
            kind="image",
            original_path="/tmp/smoke_draft_state.png",
            normalized_path=None,
            mime="image/png",
            size_bytes=1234,
            width=800,
            height=600,
            sha256=uuid.uuid4().hex,
        )
        db.add(source_asset)
        db.commit()
        db.refresh(source_asset)

        draft = Draft(
            user_id=user.id,
            source_asset_id=source_asset.id,
            crop_bbox={"x": 0, "y": 0, "w": 800, "h": 600},
            status=DraftStatus.DRAFT_CREATED,
            current_content=None,
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)

        create_draft_event(
            db,
            draft_id=draft.id,
            from_status=None,
            to_status=DraftStatus.DRAFT_CREATED,
            event_type=DraftEventType.CREATE,
            metadata={"source": "smoke_test"},
            commit=False,
        )

        transition_draft_status(
            db,
            draft,
            DraftStatus.RECOGNIZING,
            DraftEventType.START_RECOGNIZE,
            metadata={"reason": "smoke_test"},
            commit=False,
        )

        transition_draft_status(
            db,
            draft,
            DraftStatus.DRAFT_READY,
            DraftEventType.RECOGNIZE_SUCCESS,
            metadata={"reason": "smoke_test"},
            commit=False,
        )

        db.commit()
        db.refresh(draft)

        events = (
            db.query(DraftEvent)
            .filter(DraftEvent.draft_id == draft.id)
            .order_by(DraftEvent.created_at.asc(), DraftEvent.id.asc())
            .all()
        )
        event_count = len(events)
        if event_count < 3:
            details = ", ".join(
                f"{event.event_type}/{event.from_status}->{event.to_status}"
                for event in events
            )
            print(f"draft_id={draft.id} events=[{details}]")
            raise RuntimeError("draft_events < 3")

        expected = [
            (DraftEventType.CREATE, DraftStatus.DRAFT_CREATED),
            (DraftEventType.START_RECOGNIZE, DraftStatus.RECOGNIZING),
            (DraftEventType.RECOGNIZE_SUCCESS, DraftStatus.DRAFT_READY),
        ]
        for index, (expected_type, expected_status) in enumerate(expected):
            event = events[index]
            if event.event_type != expected_type or event.to_status != expected_status:
                details = ", ".join(
                    f"{event.event_type}/{event.from_status}->{event.to_status}"
                    for event in events
                )
                print(f"draft_id={draft.id} events=[{details}]")
                raise RuntimeError(
                    f"draft_event[{index}] expected {expected_type}/{expected_status}"
                )

        print(f"draft_id={draft.id} draft_events={event_count} OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
