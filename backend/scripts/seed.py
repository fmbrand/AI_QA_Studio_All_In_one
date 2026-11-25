"""Create a demo user and a demo project with synthetic data. Safe to run more than once.

    uv run python scripts/seed.py

SEED_EMAIL and SEED_PASSWORD override the defaults. Without SEED_PASSWORD a random password is
generated and printed once. All content is synthetic.
"""

import io
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import UploadFile  # noqa: E402

from app.database.session import get_session_factory  # noqa: E402
from app.repositories.access import get_project_access  # noqa: E402
from app.schemas.projects import ModuleCreateIn, ProjectCreateIn  # noqa: E402
from app.services import auth, documents, modules, projects  # noqa: E402

REQUIREMENTS = """# Service Booking — Booking module (synthetic sample)

REQ: A customer can create a booking for an available time slot.
REQ: Past dates cannot be selected in the date picker.
REQ: A customer can apply one eligible coupon per booking.
REQ: An expired coupon shows a validation message and is not applied.
REQ: A provider can accept or reject a pending booking within 24 hours.
"""


async def _stage(name: str, content: bytes) -> documents.StagedFile:
    return await documents.stage_upload(UploadFile(filename=name, file=io.BytesIO(content)))


def main() -> None:
    import asyncio

    email = os.environ.get("SEED_EMAIL", "demo@aiqa.local")
    password = os.environ.get("SEED_PASSWORD") or secrets.token_urlsafe(12)
    factory = get_session_factory()
    with factory() as db:
        user = auth.find_user_by_email(db, email)
        if user:
            print(f"Demo user {email} already exists; nothing to do.")
            return
        user = auth.register(db, email, "Demo QA Engineer", password)
        project = projects.create_project(
            db,
            user,
            ProjectCreateIn(
                name="Service Booking (demo)",
                platform="multi_platform",
                project_type="Marketplace",
                business_domain="Home services",
                description="Synthetic demo project: customers book home-service providers.",
                tech_stack=["Laravel", "React", "Flutter"],
            ),
        )
        db.flush()
        access = get_project_access(db, project.id, user.id)
        assert access is not None
        created = {
            name: modules.create_module(db, access, user, ModuleCreateIn(name=name, description=desc))
            for name, desc in [
                ("Booking", "Search slots, create and manage bookings"),
                ("Coupons", "Discount codes and eligibility rules"),
                ("Payments", "Checkout and payment methods"),
            ]
        }
        db.flush()
        modules.set_connections(
            db, access, user, created["Booking"].id, [created["Coupons"].id, created["Payments"].id]
        )
        staged = asyncio.run(_stage("booking-requirements.md", REQUIREMENTS.encode()))
        try:
            documents.create_document(
                db,
                access,
                user,
                staged,
                title="Booking requirements",
                kind="requirement",
                module_id=created["Booking"].id,
            )
        finally:
            staged.cleanup()
        db.commit()
    print(f"Created demo user {email}")
    if not os.environ.get("SEED_PASSWORD"):
        print(f"Generated password (shown once): {password}")
    print("Start the worker (python -m app.worker) to process the demo document.")


if __name__ == "__main__":
    main()
