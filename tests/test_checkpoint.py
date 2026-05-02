from __future__ import annotations

import asyncio

from investment_tracker.api.main import create_app


def test_checkpoint_health_and_openapi() -> None:
    app = create_app()
    health_route = next(route for route in app.routes if getattr(route, "path", None) == "/health")

    health_result = asyncio.run(health_route.endpoint())
    assert health_result == {"status": "ok"}

    payload = app.openapi()
    assert payload["info"]["title"] == "Intelligent Investment Tracker"
    assert "/api/transactions" in payload["paths"]
