"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from investment_tracker.api.routes.advice import router as advice_router
from investment_tracker.api.routes.exchange_rates import router as exchange_rates_router
from investment_tracker.api.routes.performance import router as performance_router
from investment_tracker.api.routes.positions import router as positions_router
from investment_tracker.api.routes.transactions import router as transactions_router
from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.orchestration.container import OrchestrationContainer
from investment_tracker.settings import get_settings
from investment_tracker.utils.ai_client import AIClient
from investment_tracker.utils.logger import configure_logging


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.orchestration = OrchestrationContainer.build(ai_client=AIClient())
    yield


def create_app() -> FastAPI:
    configure_logging(get_settings())

    app = FastAPI(
        title="Intelligent Investment Tracker",
        version="0.2.0",
        description="REST API for multi-currency investment tracking.",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ToolExecutionError)
    async def tool_error_handler(request: Request, exc: ToolExecutionError) -> JSONResponse:
        return JSONResponse(status_code=400, content=exc.to_dict())

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(transactions_router)
    app.include_router(positions_router)
    app.include_router(performance_router)
    app.include_router(advice_router)
    app.include_router(exchange_rates_router)
    return app


app = create_app()
