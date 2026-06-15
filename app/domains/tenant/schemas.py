"""Pydantic schemas for the Tenant resource.

NOTE: Implementation is deferred to Step 9. The slug format constraint
on ``tenant_code`` will be enforced here via a Pydantic ``field_validator``
matching the DB CHECK in ``app/db/models/tenant.py``:

    regex:  ^[a-z0-9]+(-[a-z0-9]+)*$
    length: 3-32
"""
