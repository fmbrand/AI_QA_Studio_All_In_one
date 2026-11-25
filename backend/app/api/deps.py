"""Request dependencies: the current user and project-role checks."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models import User
from app.models.project import ROLE_RANK
from app.repositories.access import ProjectAccess, get_project_access

_bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> User:
    unauthorized = AppError(401, "unauthorized", "Sign in to continue", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_project_role(min_role: str) -> Callable[..., ProjectAccess]:
    """Dependency factory. Non-members get 404 (the project's existence is not confirmed);
    members below `min_role` get 403."""
    needed = ROLE_RANK[min_role]

    def dependency(
        db: DB, user: CurrentUser, project_id: Annotated[uuid.UUID, Path()], request: Request
    ) -> ProjectAccess:
        access = get_project_access(db, project_id, user.id)
        if access is None:
            raise AppError(404, "not_found", "Project not found")
        if access.rank < needed:
            raise AppError(403, "forbidden", f"This action needs the {min_role.replace('_', ' ')} role or higher")
        request.state.project_id = project_id
        return access

    return dependency


Viewer = Annotated[ProjectAccess, Depends(require_project_role("viewer"))]
Engineer = Annotated[ProjectAccess, Depends(require_project_role("qa_engineer"))]
Admin = Annotated[ProjectAccess, Depends(require_project_role("admin"))]
Owner = Annotated[ProjectAccess, Depends(require_project_role("owner"))]
