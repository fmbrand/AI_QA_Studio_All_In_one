"""Import every model so Alembic and the metadata see the full schema."""

from app.models.activity import ActivityLog
from app.models.ai import AIGeneration, AIPromptVersion
from app.models.context import ContextChunk
from app.models.document import DocumentExtraction, DocumentVersion, UploadedDocument
from app.models.job import Job
from app.models.project import Module, ModuleConnection, Project, ProjectMember, Role
from app.models.requirement import KeyCounter, Requirement, RequirementVersion
from app.models.user import RefreshToken, User

__all__ = [
    "AIGeneration",
    "AIPromptVersion",
    "ActivityLog",
    "ContextChunk",
    "DocumentExtraction",
    "DocumentVersion",
    "Job",
    "KeyCounter",
    "Module",
    "ModuleConnection",
    "Project",
    "ProjectMember",
    "RefreshToken",
    "Requirement",
    "RequirementVersion",
    "Role",
    "UploadedDocument",
    "User",
]
