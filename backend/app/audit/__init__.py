"""Append-only audit event writer and reader.

There is deliberately no update or delete path in this package. The initial
migration additionally installs a PostgreSQL trigger that raises on UPDATE or
DELETE against ``audit_events``, so history cannot be rewritten even by a direct
SQL statement.
"""

from app.audit.writer import record_audit_event

__all__ = ["record_audit_event"]
