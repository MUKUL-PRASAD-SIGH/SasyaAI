"""FastAPI entry point for the SasyaAI demonstrator."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.models.advisory import (
    AdvisoryResponse,
    HITLCase,
    HITLDecisionRequest,
    MemorySearchRequest,
    QueryRequest,
)
from app.services.advisory import (
    AdvisoryService,
    ConsentNotGrantedError,
    FarmerNotFoundError,
    HITLCaseNotPendingError,
)


def create_app(runtime_dir: Path | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SasyaAI API",
        version="0.1.0",
        description="Synthetic-data, safety-gated demonstrator for SasyaAI.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.advisory_service = AdvisoryService(settings=settings, runtime_dir=runtime_dir)

    def service() -> AdvisoryService:
        return app.state.advisory_service

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.app_environment,
        }

    @app.post("/api/v1/query", response_model=AdvisoryResponse, tags=["advisory"])
    def submit_query(request: QueryRequest) -> AdvisoryResponse:
        try:
            return service().query(request)
        except FarmerNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown demo farmer ID."
            ) from error
        except ConsentNotGrantedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Advisory consent has not been granted for this demo farmer.",
            ) from error

    @app.get("/api/v1/farmers/{farmer_id}", tags=["farmers"])
    def get_farmer(farmer_id: str) -> dict[str, object]:
        try:
            return service().get_farmer(farmer_id)
        except FarmerNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown demo farmer ID."
            ) from error
        except ConsentNotGrantedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Advisory consent has not been granted for this demo farmer.",
            ) from error

    @app.post("/api/v1/memory/search", tags=["memory"])
    def search_memory(request: MemorySearchRequest) -> list[dict[str, object]]:
        try:
            return service().search_memory(request)
        except FarmerNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown demo farmer ID."
            ) from error
        except ConsentNotGrantedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Advisory consent has not been granted for this demo farmer.",
            ) from error

    @app.post(
        "/api/v1/hitl/{case_id}/decision", response_model=HITLCase, tags=["human-in-the-loop"]
    )
    def decide_hitl(case_id: str, request: HITLDecisionRequest) -> HITLCase:
        try:
            case = service().decide_hitl(case_id, request)
        except HITLCaseNotPendingError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This HITL case has already received a decision.",
            ) from error
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown HITL case ID."
            )
        return case

    @app.get("/api/v1/hitl", response_model=list[HITLCase], tags=["human-in-the-loop"])
    def list_hitl_cases() -> list[HITLCase]:
        return service().list_hitl_cases()

    return app


app = create_app()
