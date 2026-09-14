from decimal import Decimal


VALID_ORDER_STATUSES = frozenset({"submitted", "approved", "completed"})


def order_line_total(order) -> Decimal:
    return sum(
        (Decimal(str(item.quantity or 0)) * Decimal(str(item.unit_price or 0)) for item in order.items),
        Decimal("0"),
    ).quantize(Decimal("0.01"))


def order_is_consistent(order) -> bool:
    if order.status not in VALID_ORDER_STATUSES or not order.items:
        return False
    for item in order.items:
        expected = (Decimal(str(item.quantity or 0)) * Decimal(str(item.unit_price or 0))).quantize(Decimal("0.01"))
        if Decimal(str(item.amount or 0)).quantize(Decimal("0.01")) != expected:
            return False
    return Decimal(str(order.total_amount or 0)).quantize(Decimal("0.01")) == order_line_total(order)
