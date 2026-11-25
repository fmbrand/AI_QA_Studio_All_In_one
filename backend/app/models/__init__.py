"""Import every model so Alembic and the metadata see the full schema."""

from app.models.activity import ActivityLog
from app.models.document import DocumentExtraction, DocumentVersion, UploadedDocument
from app.models.job import Job
from app.models.project import Module, ModuleConnection, Project, ProjectMember, Role
from app.models.user import RefreshToken, User

__all__ = [
    "ActivityLog",
    "DocumentExtraction",
    "DocumentVersion",
    "Job",
    "Module",
    "ModuleConnection",
    "Project",
    "ProjectMember",
    "RefreshToken",
    "Role",
    "UploadedDocument",
    "User",
]
