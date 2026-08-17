from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Organization, OrganizationType, User, UserRole
from .security import hash_password


DEFAULT_ORGANIZATIONS = [
    ("УМБАЛ Св. Иван Рилски - София", 1, "http://hospital-a:8000"),
    ("УМБАЛ Св. Георги - Пловдив", 2, "http://hospital-b:8000"),
    ("УМБАЛ Св. Марина - Варна", 3, "http://hospital-c:8000"),
    ("УМБАЛ Александровска - София", 4, "http://hospital-d:8000"),
    ("УМБАЛ Св. Анна - София", 5, "http://hospital-e:8000"),
    ("УМБАЛ Канев - Русе", 6, "http://hospital-f:8000"),
]


def seed_demo_data(db: Session) -> None:
    existing_orgs = {
        org.participant_index: org
        for org in db.scalars(select(Organization).where(Organization.participant_index.is_not(None)))
    }
    orgs: list[Organization] = []
    for name, index, node_url in DEFAULT_ORGANIZATIONS:
        org = existing_orgs.get(index)
        if org is None:
            org = Organization(
                name=name,
                type=OrganizationType.HOSPITAL,
                participant_index=index,
                node_url=node_url,
            )
            db.add(org)
        orgs.append(org)
    db.flush()

    if not db.scalar(select(User.id).where(User.email == "researcher@precisionmpc.example.com")):
        db.add(User(
            organization_id=orgs[0].id,
            email="researcher@precisionmpc.example.com",
            password_hash=hash_password("Research123!"),
            first_name="Demo",
            last_name="Researcher",
            role=UserRole.RESEARCHER,
        ))
    for idx, org in enumerate(orgs, start=1):
        email = f"admin{idx}@precisionmpc.example.com"
        if not db.scalar(select(User.id).where(User.email == email)):
            db.add(User(
                organization_id=org.id,
                email=email,
                password_hash=hash_password("Admin123!"),
                first_name=f"Hospital{idx}",
                last_name="Admin",
                role=UserRole.ORG_ADMIN,
            ))
    if not db.scalar(select(User.id).where(User.email == "system@precisionmpc.example.com")):
        db.add(User(
            email="system@precisionmpc.example.com",
            password_hash=hash_password("System123!"),
            first_name="System",
            last_name="Administrator",
            role=UserRole.SYSTEM_ADMIN,
        ))
    db.commit()
