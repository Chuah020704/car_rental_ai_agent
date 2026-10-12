"""Reservation lookup/modify/cancel business rules, including authorization and
idempotency guards — the structural enforcement backing the project's IDOR guardrail."""

from datetime import date

import pytest

from app.service.reservation.reservation_service import ReservationService
from app.utils.exception.exceptions import (
    InvalidStateTransitionException,
    NotAuthorizedException,
    ReservationNotFoundException,
)


def test_get_reservation_returns_match_for_owner(
    reservation_service: ReservationService,
) -> None:
    reservation = reservation_service.get_reservation("R001", customer_id="C001")
    assert reservation.reservation_id == "R001"


def test_get_reservation_rejects_other_customer(
    reservation_service: ReservationService,
) -> None:
    with pytest.raises(NotAuthorizedException):
        reservation_service.get_reservation("R001", customer_id="C999")


def test_get_reservation_raises_not_found(reservation_service: ReservationService) -> None:
    with pytest.raises(ReservationNotFoundException):
        reservation_service.get_reservation("R999", customer_id="C001")


def test_cancel_reservation_succeeds_for_owner(
    reservation_service: ReservationService,
) -> None:
    updated = reservation_service.cancel_reservation("R002", customer_id="C002")
    assert updated.status == "cancelled"
    assert updated.payment_status == "refunded"


def test_cancel_already_cancelled_reservation_rejected(
    reservation_service: ReservationService,
) -> None:
    # R005 is already CANCELLED in the fixture data — idempotency guard.
    with pytest.raises(InvalidStateTransitionException):
        reservation_service.cancel_reservation("R005", customer_id="C002")


def test_modify_reservation_recalculates_price(
    reservation_service: ReservationService,
) -> None:
    updated = reservation_service.modify_reservation(
        "R006",
        customer_id="C004",
        new_pickup_date=date(2026, 10, 21),
        new_return_date=date(2026, 10, 24),
    )
    assert updated.pickup_date == date(2026, 10, 21)
    assert updated.total_price == pytest.approx(180 * 3)


def test_modify_reservation_rejects_invalid_date_order(
    reservation_service: ReservationService,
) -> None:
    with pytest.raises(InvalidStateTransitionException):
        reservation_service.modify_reservation(
            "R006",
            customer_id="C004",
            new_pickup_date=date(2026, 10, 25),
            new_return_date=date(2026, 10, 20),
        )
