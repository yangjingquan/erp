from uuid import uuid4
import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.platform import ExtEventDelivery, ExtEventOutbox, ExtEventSubscription
from app.core.time import local_now
from app.core.exceptions import AppError


def emit_event(
    db: Session,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
    org_id: str | None = None,
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
                org_id=org_id,
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


def create_subscription(db: Session, payload: dict, org_id: str) -> tuple[ExtEventSubscription, str]:
    duplicate = db.scalar(select(ExtEventSubscription).where(
        ExtEventSubscription.org_id == org_id, ExtEventSubscription.name == payload["name"], ExtEventSubscription.is_deleted.is_(False)
    ))
    if duplicate is not None:
        raise AppError("事件订阅名称已存在", code=409)
    secret = secrets.token_urlsafe(32)
    row = ExtEventSubscription(
        org_id=org_id, name=payload["name"].strip(), endpoint_url=payload["endpoint_url"].strip(),
        event_types=payload["event_types"], secret_hash=hashlib.sha256(secret.encode()).hexdigest(), signing_secret=secret,
    )
    db.add(row); db.flush(); return row, secret


def list_subscriptions(db: Session, org_id: str) -> list[dict]:
    rows = db.scalars(select(ExtEventSubscription).where(ExtEventSubscription.org_id == org_id, ExtEventSubscription.is_deleted.is_(False)).order_by(ExtEventSubscription.created_at.desc())).all()
    return [{"id": row.id, "name": row.name, "endpoint_url": row.endpoint_url, "event_types": row.event_types, "status": row.status, "failure_count": row.failure_count} for row in rows]


def set_subscription_status(db: Session, subscription_id: str, org_id: str, status: str) -> ExtEventSubscription:
    if status not in {"active", "inactive"}:
        raise AppError("订阅状态无效", code=400)
    row = db.scalar(select(ExtEventSubscription).where(
        ExtEventSubscription.id == subscription_id,
        ExtEventSubscription.org_id == org_id,
        ExtEventSubscription.is_deleted.is_(False),
    ))
    if row is None:
        raise AppError("事件订阅不存在", code=404)
    row.status = status
    row.version += 1
    db.flush()
    return row


def dispatch_event(db: Session, event_id: str, org_id: str) -> dict:
    import httpx

    event = db.scalar(select(ExtEventOutbox).where(ExtEventOutbox.id == event_id, ExtEventOutbox.org_id == org_id, ExtEventOutbox.is_deleted.is_(False)))
    if event is None:
        raise AppError("事件不存在", code=404)
    subscriptions = db.scalars(select(ExtEventSubscription).where(ExtEventSubscription.org_id == org_id, ExtEventSubscription.status == "active", ExtEventSubscription.is_deleted.is_(False))).all()
    delivered = []
    body = json.dumps({"id": event.id, "event_type": event.event_type, "aggregate_type": event.aggregate_type, "aggregate_id": event.aggregate_id, "payload": event.payload_json}, ensure_ascii=False, separators=(",", ":"))
    for subscription in subscriptions:
        if subscription.event_types and "*" not in subscription.event_types and event.event_type not in subscription.event_types:
            continue
        delivery = db.scalar(select(ExtEventDelivery).where(ExtEventDelivery.event_id == event.id, ExtEventDelivery.subscription_id == subscription.id))
        if delivery is None:
            delivery = ExtEventDelivery(org_id=org_id, event_id=event.id, subscription_id=subscription.id)
            db.add(delivery); db.flush()
        if delivery.status == "delivered":
            delivered.append({"subscription_id": subscription.id, "status": delivery.status}); continue
        signature = hmac.new(subscription.signing_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        delivery.attempt_count += 1
        try:
            response = httpx.post(subscription.endpoint_url, content=body.encode(), headers={"Content-Type": "application/json", "X-ERP-Event": event.event_type, "X-ERP-Signature": f"sha256={signature}"}, timeout=5.0)
            delivery.response_status = response.status_code
            delivery.response_body = response.text[:1000]
            if 200 <= response.status_code < 300:
                delivery.status = "delivered"; delivery.delivered_at = local_now(); subscription.failure_count = 0
            else:
                delivery.status = "failed"; subscription.failure_count += 1
        except httpx.HTTPError as exc:
            delivery.status = "failed"; delivery.response_body = str(exc)[:1000]; subscription.failure_count += 1
        delivered.append({"subscription_id": subscription.id, "status": delivery.status, "attempt_count": delivery.attempt_count, "response_status": delivery.response_status})
    event.status = "delivered" if delivered and all(item["status"] == "delivered" for item in delivered) else ("failed" if delivered else event.status)
    event.retry_count += 1 if delivered and event.status == "failed" else 0
    event.next_retry_at = local_now() + timedelta(minutes=min(60, 2 ** min(event.retry_count, 5))) if event.status == "failed" else None
    db.flush()
    return {"event_id": event.id, "status": event.status, "deliveries": delivered}
