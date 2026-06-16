"""Standard response envelopes for success and error paths.

Two thin helpers — :func:`success_response` and :func:`error_response` —
plus :func:`jsonable_adapter`, used to coerce arbitrary Python objects
into something FastAPI's ``JSONResponse`` can serialise.

The envelope shapes are documented in the project README and are part
of the public contract. Adding a new field to either envelope is a
breaking change for clients; renaming or removing an existing one is
even worse. Treat this module as a wire-format file.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi.responses import JSONResponse


def success_response(
    data: Any,
    message: str = "Success",
    status_code: int = 200,
) -> JSONResponse:
    """Wrap a successful payload in the standard success envelope.

    Shape::

        {
            "success": true,
            "message": "<human-readable summary>",
            "data":    <payload>
        }
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data,
        },
    )


def error_response(
    code: str,
    message: str,
    details: Any = None,
    status_code: int = 400,
) -> JSONResponse:
    """Wrap a failure in the standard error envelope.

    Shape::

        {
            "success": false,
            "error": {
                "code":    "<stable error code>",
                "message": "<human-readable summary>",
                "details": <optional structured context>
            }
        }
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
        },
    )


def jsonable_adapter(value: Any) -> Any:
    """Recursively coerce ``value`` into something ``JSONResponse`` can encode.

    ``JSONResponse`` uses the stdlib ``json`` module, which chokes on
    common non-primitive types (exceptions, sets, custom classes,
    bytes, Decimal, etc.). The two common offenders in our codebase:

    - :class:`fastapi.exceptions.RequestValidationError` —
      ``exc.errors()`` may include a ``ctx`` dict whose ``error`` key
      holds the original ``ValueError`` raised by a Pydantic
      ``field_validator``.
    - Any ORM object passed by mistake.

    Strategy: descend into dicts / lists / tuples, preserve primitives,
    stringify anything else (``str(exc)`` for exceptions is more useful
    than ``"<MyError ...>"``). Keeps the envelope shape intact while
    preventing the response handler from itself raising.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(k): jsonable_adapter(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable_adapter(item) for item in value]
    if isinstance(value, BaseException):
        # ``str(exc)`` is the message without the surrounding
        # ``ValueError: `` prefix; full ``repr`` includes the class
        # name which makes log scraping easier.
        return f"{type(value).__name__}: {value}"
    return str(value)
