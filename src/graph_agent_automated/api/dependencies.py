from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from graph_agent_automated.application.services import AgentOptimizationService
from graph_agent_automated.core.config import Settings, get_settings
from graph_agent_automated.core.database import get_db
from graph_agent_automated.infrastructure.runtime.job_queue import InMemoryJobQueue

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"versions:read"},
    "operator": {"versions:read", "optimize:run", "parity:run"},
    "admin": {
        "versions:read",
        "versions:deploy",
        "versions:rollback",
        "optimize:run",
        "parity:run",
    },
}

JOB_QUEUE = InMemoryJobQueue()


@dataclass(frozen=True)
class AuthContext:
    principal: str
    tenant_id: str
    role: str

    @property
    def permissions(self) -> set[str]:
        permissions = ROLE_PERMISSIONS.get(self.role)
        if permissions is None:
            return set()
        return permissions


def get_db_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_service(session: Session = Depends(get_db_session)) -> AgentOptimizationService:
    return AgentOptimizationService(session=session, settings=get_settings())


def get_job_queue() -> InMemoryJobQueue:
    return JOB_QUEUE


def get_auth_context(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthContext:
    settings = get_settings()
    if not settings.auth_enabled:
        return AuthContext(
            principal="local-dev",
            tenant_id=settings.auth_default_tenant_id,
            role="admin",
        )

    token = _extract_bearer_token(authorization)
    if token is not None:
        return _parse_jwt_auth_context(token=token, settings=settings)

    principals = _parse_api_keys_json(settings.auth_api_keys_json)
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing credentials: provide Authorization bearer token or X-API-Key header",
        )

    context = principals.get(x_api_key)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid API key",
        )
    return context


def require_permission(permission: str):
    def dependency(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if permission not in auth.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"permission denied: {permission}",
            )
        return auth

    return dependency


def to_tenant_scoped_agent_name(agent_name: str, auth: AuthContext) -> str:
    tenant = auth.tenant_id.strip()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="invalid auth context: empty tenant_id",
        )
    return f"{tenant}::{agent_name}"


def _parse_api_keys_json(raw: str) -> dict[str, AuthContext]:
    payload = _parse_json_object(raw, setting_name="AUTH_API_KEYS_JSON")

    principals: dict[str, AuthContext] = {}
    for api_key, spec in payload.items():
        if not isinstance(api_key, str) or not api_key:
            continue

        if isinstance(spec, str):
            tenant_id = spec
            role = "admin"
            principal = api_key
        elif isinstance(spec, dict):
            tenant_id = str(spec.get("tenant_id") or "").strip()
            role = str(spec.get("role") or "").strip().lower()
            principal = str(spec.get("principal") or api_key).strip()
        else:
            continue

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"invalid AUTH_API_KEYS_JSON: tenant_id required for key {api_key}",
            )
        if role not in ROLE_PERMISSIONS:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"invalid AUTH_API_KEYS_JSON: unsupported role {role}",
            )
        principals[api_key] = AuthContext(principal=principal, tenant_id=tenant_id, role=role)

    return principals


def _parse_jwt_auth_context(token: str, settings: Settings) -> AuthContext:
    segments = token.split(".")
    if len(segments) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token format",
        )

    header_raw, payload_raw, signature_raw = segments
    header = _decode_jwt_json_segment(header_raw, segment_name="header")
    payload = _decode_jwt_json_segment(payload_raw, segment_name="payload")
    signature = _decode_base64url(signature_raw, segment_name="signature")

    algorithm = str(header.get("alg") or "")
    if algorithm != "HS256":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unsupported jwt algorithm",
        )

    signing_input = f"{header_raw}.{payload_raw}".encode("ascii")
    secret = _resolve_jwt_secret(header, settings)
    expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid jwt signature",
        )

    _validate_jwt_claims(payload, settings)

    tenant_id = str(payload.get("tenant_id") or "").strip()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid jwt claim: tenant_id required",
        )

    role = str(payload.get("role") or "").strip().lower()
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid jwt claim: unsupported role",
        )

    principal = str(payload.get("sub") or payload.get("principal") or "jwt-principal").strip()
    if not principal:
        principal = "jwt-principal"
    return AuthContext(principal=principal, tenant_id=tenant_id, role=role)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    value = authorization.strip()
    if not value:
        return None

    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid Authorization header",
        )
    return token.strip()


def _resolve_jwt_secret(header: dict[str, Any], settings: Settings) -> str:
    jwt_keys = _parse_jwt_keys_json(settings.auth_jwt_keys_json)
    if not jwt_keys:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="invalid AUTH_JWT_KEYS_JSON: no keys configured",
        )

    key_id = str(header.get("kid") or "").strip()
    if key_id:
        secret = jwt_keys.get(key_id)
        if secret is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="unknown jwt key id",
            )
        return secret

    if len(jwt_keys) == 1:
        return next(iter(jwt_keys.values()))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="jwt key id required for rotated key set",
    )


def _validate_jwt_claims(payload: dict[str, Any], settings: Settings) -> None:
    now = time.time()
    skew = float(settings.auth_jwt_clock_skew_seconds)

    exp = _read_numeric_claim(payload, "exp", required=True)
    if exp is None or now > exp + skew:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="jwt token expired",
        )

    nbf = _read_numeric_claim(payload, "nbf", required=False)
    if nbf is not None and now + skew < nbf:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="jwt token not active yet",
        )

    iat = _read_numeric_claim(payload, "iat", required=False)
    if iat is not None and iat > now + skew:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="jwt token issued in the future",
        )

    expected_issuer = settings.auth_jwt_issuer.strip()
    if expected_issuer and str(payload.get("iss") or "") != expected_issuer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid jwt issuer",
        )

    expected_audience = settings.auth_jwt_audience.strip()
    if not expected_audience:
        return

    audience_claim = payload.get("aud")
    if isinstance(audience_claim, str):
        valid = audience_claim == expected_audience
    elif isinstance(audience_claim, list):
        valid = expected_audience in [str(item) for item in audience_claim]
    else:
        valid = False

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid jwt audience",
        )


def _read_numeric_claim(
    payload: dict[str, Any],
    claim: str,
    required: bool,
) -> float | None:
    value = payload.get(claim)
    if value is None:
        if required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"invalid jwt claim: {claim} required",
            )
        return None
    if isinstance(value, bool):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid jwt claim: {claim} must be numeric",
        )
    if isinstance(value, (int, float)):
        return float(value)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"invalid jwt claim: {claim} must be numeric",
    )


def _parse_jwt_keys_json(raw: str) -> dict[str, str]:
    payload = _parse_json_object(raw, setting_name="AUTH_JWT_KEYS_JSON")
    output: dict[str, str] = {}
    for key_id, secret in payload.items():
        if not isinstance(key_id, str) or not key_id:
            continue
        if not isinstance(secret, str) or not secret.strip():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"invalid AUTH_JWT_KEYS_JSON: secret required for key {key_id}",
            )
        output[key_id] = secret
    return output


def _decode_jwt_json_segment(segment: str, segment_name: str) -> dict[str, Any]:
    raw = _decode_base64url(segment, segment_name=segment_name)
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid jwt {segment_name} segment",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid jwt {segment_name} segment",
        )
    return payload


def _decode_base64url(segment: str, segment_name: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid jwt {segment_name} encoding",
        ) from exc


def _parse_json_object(raw: str, setting_name: str) -> dict[str, Any]:
    try:
        payload: Any = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"invalid {setting_name}: {exc.msg}",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"invalid {setting_name}: root must be object",
        )
    return payload
