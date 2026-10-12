"""JWT simulation — mints a token for a customer picked from the mock data.

AUTH_MODE=entra customers authenticate directly against Microsoft Entra
instead (see app/dependencies/auth.py) and never call this endpoint; it only
exists to satisfy AUTH_MODE=simulated, the default and graded path.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.schemas import TokenRequest, TokenResponse
from app.dependencies.auth import create_access_token, get_customer_directory
from app.service.customer_directory import CustomerSummary
from app.utils.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/customers", response_model=list[CustomerSummary])
def list_customers() -> list[CustomerSummary]:
    """Lets the Streamlit UI populate a customer picker without hardcoding IDs."""
    return get_customer_directory().list_customers()


@router.post("/token", response_model=TokenResponse)
def issue_token(payload: TokenRequest) -> TokenResponse:
    customer = get_customer_directory().find_by_customer_id(payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown customer_id")

    settings = get_settings()
    token = create_access_token(customer.customer_id, customer.customer_name, settings)
    return TokenResponse(
        access_token=token,
        customer_id=customer.customer_id,
        customer_name=customer.customer_name,
    )
