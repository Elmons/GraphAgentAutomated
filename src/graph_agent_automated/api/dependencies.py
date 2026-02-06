from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from graph_agent_automated.application.services import AgentOptimizationService
from graph_agent_automated.core.config import get_settings
from graph_agent_automated.core.database import get_db

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


def get_auth_context(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthContext:
    settings = get_settings()
    if not settings.auth_enabled:
        return AuthContext(
            principal="local-dev",
            tenant_id=settings.auth_default_tenant_id,
            role="admin",
        )

    principals = _parse_api_keys_json(settings.auth_api_keys_json)
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-API-Key header",
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
    try:
        payload: Any = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"invalid AUTH_API_KEYS_JSON: {exc.msg}",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="invalid AUTH_API_KEYS_JSON: root must be object",
        )

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
