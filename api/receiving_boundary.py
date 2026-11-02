"""Bounded request bodies and a customer profile that never serves legacy demo APIs."""
import os
from starlette.responses import JSONResponse


class ReceivingBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        customer = os.getenv("SITEPULSE_MODE") == "customer"
        allowed = (path in {"/", "/receive", "/receive-sw.js", "/readyz"}
                   or path.startswith("/receiving/")
                   or path in {"/static/receiving.js", "/static/receiving.css", "/static/receiving.html",
                               "/static/design/tokens.css", "/static/design/mark.svg"})
        if customer and not allowed:
            return await JSONResponse({"detail": "Legacy demonstration API disabled in customer mode"}, 404)(scope, receive, send)
        if path.startswith("/receiving/") and scope["method"] in {"POST", "PUT", "PATCH"}:
            cap = 6 * 1024 * 1024 if path.endswith("/attachments") else 256 * 1024
            chunks, size = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > cap:
                    return await JSONResponse({"detail": "Receiving request too large"}, 413)(scope, receive, send)
                chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            delivered = False
            original_receive = receive

            async def bounded_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
                return await original_receive()
            receive = bounded_receive

        async def private_send(message):
            if message["type"] == "http.response.start" and path.startswith("/receiving/"):
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
                message["headers"] = headers + [(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
            await send(message)
        await self.app(scope, receive, private_send)
