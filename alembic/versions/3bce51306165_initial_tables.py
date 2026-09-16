"""initial migration marker

Revision ID: 3bce51306165
Revises:
Create Date: 2026-03-27 20:47:46.556916
"""

from typing import Sequence, Union


revision: str = "3bce51306165"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Preserve the repository's already-issued initial revision."""
    pass


def downgrade() -> None:
    pass
