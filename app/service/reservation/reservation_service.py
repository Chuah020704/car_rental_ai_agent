"""Reservation lookup/modify/cancel business logic.

All authorization (does this customer own this reservation?) and state-machine
rules (can't cancel an already-cancelled reservation, etc.) live here — never in
an agent tool, and never trusted to the LLM. See AGENTS.md's security section.
"""

from datetime import date

from app.enums import PaymentStatus, ReservationStatus
from app.models.schemas import Reservation
from app.repositories.base import ReservationRepository, VehicleRepository
from app.utils.exception.exceptions import (
    InvalidStateTransitionException,
    NotAuthorizedException,
    ReservationNotFoundException,
    VehicleNotFoundException,
)
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


def _dates_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    """Two date ranges overlap unless one ends before the other starts."""
    return a_start <= b_end and b_start <= a_end


class ReservationService:
    """Business rules for viewing, modifying, and cancelling reservations."""

    def __init__(
        self, reservation_repo: ReservationRepository, vehicle_repo: VehicleRepository
    ) -> None:
        self._reservation_repo = reservation_repo
        self._vehicle_repo = vehicle_repo

    def get_reservation(self, reservation_id: str, customer_id: str) -> Reservation:
        reservation = self._reservation_repo.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationNotFoundException(detail=f"{reservation_id} not found")
        self._assert_owner(reservation, customer_id)
        return reservation

    def estimate_cancellation_fee(self, reservation: Reservation) -> float:
        """Simplified version of the published cancellation policy
        (data/policies/cancellation.md): free 2+ days before pickup, one
        day's rate otherwise. Date-granularity only (no time-of-day), since
        the mock domain doesn't track pickup times — see docs/adr.
        """
        vehicle = self._vehicle_repo.get_by_id(reservation.vehicle_id)
        if vehicle is None:
            return 0.0
        days_until_pickup = (reservation.pickup_date - date.today()).days
        return 0.0 if days_until_pickup >= 2 else vehicle.price_per_day

    def cancel_reservation(self, reservation_id: str, customer_id: str) -> Reservation:
        reservation = self.get_reservation(reservation_id, customer_id)
        if reservation.status != ReservationStatus.CONFIRMED:
            raise InvalidStateTransitionException(
                detail=f"{reservation_id} is already {reservation.status}, cannot cancel"
            )
        updated = reservation.model_copy(
            update={
                "status": ReservationStatus.CANCELLED,
                "payment_status": PaymentStatus.REFUNDED,
            }
        )
        self._reservation_repo.save(updated)
        logger.info(
            "reservation_cancelled", reservation_id=reservation_id, customer_id=customer_id
        )
        return updated

    def modify_reservation(
        self,
        reservation_id: str,
        customer_id: str,
        new_pickup_date: date,
        new_return_date: date,
    ) -> Reservation:
        """Change pickup/return dates only.

        Vehicle or passenger-count changes are out of scope by design — see
        docs/adr/0003-modify-reservation-scope.md; the agent tells the
        customer to cancel and rebook instead.
        """
        reservation = self.get_reservation(reservation_id, customer_id)
        if reservation.status != ReservationStatus.CONFIRMED:
            raise InvalidStateTransitionException(
                detail=f"{reservation_id} is {reservation.status}, cannot modify"
            )
        if new_return_date <= new_pickup_date:
            raise InvalidStateTransitionException(detail="return date must be after pickup date")

        vehicle = self._vehicle_repo.get_by_id(reservation.vehicle_id)
        if vehicle is None:
            raise VehicleNotFoundException(detail=f"{reservation.vehicle_id} not found")

        conflicting = self._reservation_repo.list_active_for_vehicle(
            reservation.vehicle_id, exclude_reservation_id=reservation_id
        )
        if any(
            _dates_overlap(new_pickup_date, new_return_date, r.pickup_date, r.return_date)
            for r in conflicting
        ):
            raise InvalidStateTransitionException(
                detail=f"{reservation.vehicle_id} is not available for the new dates"
            )

        days = (new_return_date - new_pickup_date).days
        updated = reservation.model_copy(
            update={
                "pickup_date": new_pickup_date,
                "return_date": new_return_date,
                "total_price": vehicle.price_per_day * days,
            }
        )
        self._reservation_repo.save(updated)
        logger.info(
            "reservation_modified",
            reservation_id=reservation_id,
            customer_id=customer_id,
            new_pickup_date=str(new_pickup_date),
            new_return_date=str(new_return_date),
        )
        return updated

    def _assert_owner(self, reservation: Reservation, customer_id: str) -> None:
        if reservation.customer_id != customer_id:
            logger.warning(
                "reservation_authorization_denied",
                reservation_id=reservation.reservation_id,
                requested_by=customer_id,
            )
            raise NotAuthorizedException(
                detail=f"customer {customer_id} does not own {reservation.reservation_id}",
                user_message="No reservation found for your account with that ID.",
            )
