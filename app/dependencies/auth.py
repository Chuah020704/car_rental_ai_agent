"""Authentication dependency — the ONLY place customer identity is ever
established from an incoming request. Dispatches on settings.auth.auth_mode:

- simulated (default, satisfies the brief's "JWT token simulation" requirement):
  decode a locally-signed JWT minted by POST /auth/token.
- entra (practice mode): validate a real Microsoft Entra ID token against
  Entra's public JWKS, then map the token's UPN to a customer_id via
  CustomerDirectory (Q13) — never trust a customer_id from the token itself.

Agent tools never see the raw token — only the customer_id this function
derives from it, injected into graph state. See AGENTS.md's security section.
"""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel

from app.agent.deps import get_reservation_repo
from app.service.customer_directory import CustomerDirectory
from app.utils.config import Settings, get_settings
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


class CurrentCustomer(BaseModel):
    customer_id: str
    customer_name: str


@lru_cache
def get_customer_directory() -> CustomerDirectory:
    return CustomerDirectory(get_reservation_repo())


@lru_cache
def _get_jwk_client(tenant_id: str) -> PyJWKClient:
    return PyJWKClient(f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys")


def create_access_token(customer_id: str, customer_name: str, settings: Settings) -> str:
    """Mint a locally-signed JWT — AUTH_MODE=simulated only."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.auth.jwt_expire_minutes)
    claims = {"sub": customer_id, "name": customer_name, "exp": expire}
    return jwt.encode(claims, settings.auth.jwt_secret_key, algorithm=settings.auth.jwt_algorithm)


def _decode_simulated_token(token: str, settings: Settings) -> CurrentCustomer:
    try:
        claims = jwt.decode(
            token, settings.auth.jwt_secret_key, algorithms=[settings.auth.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc
    return CurrentCustomer(customer_id=claims["sub"], customer_name=claims["name"])


def _decode_entra_token(token: str, settings: Settings) -> CurrentCustomer:
    """Validate an Entra ID *token* (not an access token — see docs/adr): its
    audience is this app's own client_id, which is what makes it valid for us
    to verify, unlike a Graph-audienced access token."""
    tenant_id = settings.entra.entra_tenant_id
    client_id = settings.entra.entra_client_id
    try:
        signing_key = _get_jwk_client(tenant_id).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Entra token"
        ) from exc

    upn = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
    customer = get_customer_directory().find_by_upn(upn) if upn else None
    if customer is None:
        logger.warning("entra_upn_not_linked", upn=upn)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No reservations linked to this account.",
        )
    return CurrentCustomer(customer_id=customer.customer_id, customer_name=customer.customer_name)


def get_current_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentCustomer:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    settings = get_settings()
    if settings.auth.auth_mode == "entra":
        return _decode_entra_token(credentials.credentials, settings)
    return _decode_simulated_token(credentials.credentials, settings)
