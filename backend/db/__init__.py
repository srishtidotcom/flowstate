"""Canonical SQLAlchemy database package.

Repository functions accept an explicit session and never own transactions.
Service and core layers own transaction completion through ``get_db``.
"""
