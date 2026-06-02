from app.core.constants import normalize_event_type, normalize_status
from app.db.session import SessionLocal
from app.models.draft import Draft
from app.models.draft_event import DraftEvent


def main() -> None:
    db = SessionLocal()
    try:
        drafts_updated = 0
        for draft in db.query(Draft).all():
            normalized = normalize_status(draft.status)
            if normalized != draft.status:
                draft.status = normalized
                drafts_updated += 1

        events_updated = 0
        for event in db.query(DraftEvent).all():
            updated = False
            if event.from_status is not None:
                normalized_from = normalize_status(event.from_status)
                if normalized_from != event.from_status:
                    event.from_status = normalized_from
                    updated = True

            normalized_to = normalize_status(event.to_status)
            if normalized_to != event.to_status:
                event.to_status = normalized_to
                updated = True

            normalized_type = normalize_event_type(event.event_type)
            if normalized_type != event.event_type:
                event.event_type = normalized_type
                updated = True

            if updated:
                events_updated += 1

        if drafts_updated or events_updated:
            db.commit()

        print(f"drafts_updated={drafts_updated} events_updated={events_updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
