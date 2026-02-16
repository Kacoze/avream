from __future__ import annotations

import logging
import time
from uuid import uuid4

from aiohttp import web

from avreamd.api.errors import ApiError
from avreamd.core.state_store import InvalidTransitionError
from avreamd.api.schemas import error_envelope


logger = logging.getLogger(__name__)


@web.middleware
async def request_context_middleware(request: web.Request, handler: web.RequestHandler) -> web.StreamResponse:
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request["request_id"] = request_id
    started = time.monotonic()
    logger.info("request.start rid=%s method=%s path=%s", request_id, request.method, request.path)

    try:
        response = await handler(request)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "request.done rid=%s method=%s path=%s status=%s elapsed_ms=%s",
            request_id,
            request.method,
            request.path,
            getattr(response, "status", "?"),
            elapsed_ms,
        )
        return response
    except ApiError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "request.error rid=%s method=%s path=%s code=%s status=%s elapsed_ms=%s",
            request_id,
            request.method,
            request.path,
            exc.code,
            exc.status,
            elapsed_ms,
        )
        return web.json_response(
            error_envelope(
                request_id=request_id,
                code=exc.code,
                message=exc.message,
                details=exc.details,
                retryable=exc.retryable,
            ),
            status=exc.status,
        )
    except web.HTTPException:
        raise
    except InvalidTransitionError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "request.invalid_transition rid=%s method=%s path=%s elapsed_ms=%s error=%s",
            request_id,
            request.method,
            request.path,
            elapsed_ms,
            exc,
        )
        return web.json_response(
            error_envelope(
                request_id=request_id,
                code="E_CONFLICT",
                message=str(exc),
                details={},
                retryable=True,
            ),
            status=409,
        )
    except Exception as exc:  # pragma: no cover - guardrail path
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.exception(
            "request.crash rid=%s method=%s path=%s elapsed_ms=%s error=%s",
            request_id,
            request.method,
            request.path,
            elapsed_ms,
            exc,
        )
        return web.json_response(
            error_envelope(
                request_id=request_id,
                code="E_INTERNAL",
                message="Internal server error",
                details={},
                retryable=False,
            ),
            status=500,
        )
