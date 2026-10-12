"""Lightweight customer directory derived from the mock reservation data.

Stands in for a real customer/identity service: AUTH_MODE=simulated uses it
to mint a token for a picked customer_id; AUTH_MODE=entra uses it to map an
authenticated Entra UPN back to this project's customer_id (see Q13 in the
planning notes — Entra identities don't match our mock customer IDs natively).
"""

from pydantic import BaseModel

from app.repositories.base import ReservationRepository


class CustomerSummary(BaseModel):
    customer_id: str
    customer_name: str
    entra_upn: str | None = None


class CustomerDirectory:
    def __init__(self, reservation_repo: ReservationRepository) -> None:
        self._reservation_repo = reservation_repo

    def list_customers(self) -> list[CustomerSummary]:
        """Unique customers, derived from distinct customer_id values across
        all reservations."""
        seen: dict[str, CustomerSummary] = {}
        for reservation in self._reservation_repo.get_all():
            if reservation.customer_id not in seen:
                seen[reservation.customer_id] = CustomerSummary(
                    customer_id=reservation.customer_id,
                    customer_name=reservation.customer_name,
                    entra_upn=reservation.entra_upn,
                )
        return list(seen.values())

    def find_by_customer_id(self, customer_id: str) -> CustomerSummary | None:
        return next(
            (c for c in self.list_customers() if c.customer_id == customer_id), None
        )

    def find_by_upn(self, upn: str) -> CustomerSummary | None:
        upn_lower = upn.lower()
        return next(
            (c for c in self.list_customers() if (c.entra_upn or "").lower() == upn_lower),
            None,
        )
