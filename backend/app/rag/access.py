"""Access-control predicates for knowledge retrieval (applied in SQL)."""

from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.sql import ColumnElement

from app.models import DocumentAccessLevel, KnowledgeDocument, User


def document_visible_to(user: User) -> ColumnElement[bool]:
    """SQL filter: only documents the authenticated demo user may see."""
    return and_(
        KnowledgeDocument.is_active.is_(True),
        or_(
            KnowledgeDocument.access_level == DocumentAccessLevel.PUBLIC,
            KnowledgeDocument.access_level == DocumentAccessLevel.AUTHENTICATED,
            and_(
                KnowledgeDocument.access_level == DocumentAccessLevel.RESTRICTED,
                KnowledgeDocument.access_allowlist.contains([user.demo_key]),
            ),
        ),
    )
