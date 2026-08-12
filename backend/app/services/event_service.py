from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.platform import ExtEventOutbox
from app.core.time import local_now


def emit_event(
    db: Session,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
) -> ExtEventOutbox:
    event = db.scalar(
        select(ExtEventOutbox).where(
            ExtEventOutbox.event_type == event_type,
            ExtEventOutbox.aggregate_type == aggregate_type,
            ExtEventOutbox.aggregate_id == aggregate_id,
        )
    )
    if event is not None:
        return event

    try:
        with db.begin_nested():
            event = ExtEventOutbox(
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload_json=payload,
            )
            db.add(event)
            db.flush()
    except IntegrityError:
        event = db.scalar(
            select(ExtEventOutbox).where(
                ExtEventOutbox.event_type == event_type,
                ExtEventOutbox.aggregate_type == aggregate_type,
                ExtEventOutbox.aggregate_id == aggregate_id,
            ).with_for_update()
        )
        if event is not None:
            return event
        raise
    return event


def claim_pending_events(db: Session, limit: int = 50) -> list[ExtEventOutbox]:
    if limit <= 0:
        return []

    now = local_now()
    candidate_ids = db.scalars(
        select(ExtEventOutbox.id)
        .where(
            ExtEventOutbox.status == "pending",
            ExtEventOutbox.is_deleted.is_(False),
            or_(
                ExtEventOutbox.next_retry_at.is_(None),
                ExtEventOutbox.next_retry_at <= now,
            ),
        )
        .order_by(ExtEventOutbox.created_at, ExtEventOutbox.id)
        .limit(limit)
    ).all()
    if not candidate_ids:
        return []

    claim_token = str(uuid4())
    db.execute(
        update(ExtEventOutbox)
        .where(
            ExtEventOutbox.id.in_(candidate_ids),
            ExtEventOutbox.status == "pending",
            ExtEventOutbox.is_deleted.is_(False),
            or_(
                ExtEventOutbox.next_retry_at.is_(None),
                ExtEventOutbox.next_retry_at <= now,
            ),
        )
        .values(status="processing", claim_token=claim_token)
    )
    db.flush()
    return db.scalars(
        select(ExtEventOutbox)
        .where(ExtEventOutbox.claim_token == claim_token)
        .order_by(ExtEventOutbox.created_at, ExtEventOutbox.id)
    ).all()
