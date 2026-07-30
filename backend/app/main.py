"""FastAPI entry point for the SasyaAI demo and production runtimes."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.models.advisory import (
    AdvisoryResponse,
    AgentDescriptor,
    DemoFarmerSummary,
    HITLCase,
    HITLDecisionRequest,
    KnowledgeIngestRequest,
    KnowledgeStats,
    MemorySearchRequest,
    QueryRequest,
)
from app.models.security import DeletionRequest, Principal, Role
from app.services.advisory import (
    AdvisoryService,
    ConsentNotGrantedError,
    FarmerNotFoundError,
    HITLCaseNotPendingError,
    HITLCaseSafetyBlockedError,
)
from app.services.agents import agent_descriptors
from app.services.consent import ConsentAdapterUnavailableError
from app.services.memory import LocalAuditLog, LocalDeletionRequestStore, RuntimeStateError
from app.services.observability import configure_observability
from app.services.persistence import (
    PersistenceUnavailableError,
    PostgresAuditLog,
    PostgresDeletionRequestStore,
)
from app.services.production import ProductionAdvisoryService
from app.services.resilience import ProviderUnavailableError
from app.services.security import (
    ApiKeyAuthorizer,
    AuthenticationError,
    AuthorizationError,
    RateLimitExceededError,
    RateLimitPolicy,
    SlidingWindowRateLimiter,
)


def create_app(runtime_dir: Path | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configuration_errors = settings.production_configuration_errors()
    if configuration_errors:
        raise RuntimeError(
            "Production runtime cannot start until these settings are configured: "
            + ", ".join(configuration_errors)
        )
    app = FastAPI(
        title="SasyaAI API",
        version=settings.service_version,
        description="Safety-gated agricultural advisory platform for Indian farmers.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    configure_observability(app, settings)
    active_runtime_dir = runtime_dir or settings.runtime_dir
    if settings.runtime_mode == "production":
        production_service = ProductionAdvisoryService(settings=settings)
        app.state.advisory_service = production_service
        app.state.audit_log = PostgresAuditLog(production_service.memory)
        app.state.deletion_requests = PostgresDeletionRequestStore(production_service.memory)
    else:
        app.state.advisory_service = AdvisoryService(settings=settings, runtime_dir=active_runtime_dir)
        app.state.audit_log = LocalAuditLog(active_runtime_dir)
        app.state.deletion_requests = LocalDeletionRequestStore(active_runtime_dir)
    app.state.authorizer = ApiKeyAuthorizer(
        auth_required=settings.auth_required,
        credential_json=settings.auth_principals_json,
        environment=settings.app_environment,
    )
    app.state.rate_limiter = SlidingWindowRateLimiter(
        RateLimitPolicy(
            requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
    )
    @app.exception_handler(RuntimeStateError)
    def runtime_state_error_handler(_: Request, __: RuntimeStateError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Local demonstrator state is unavailable; no advisory was delivered."
            },
        )

    @app.exception_handler(PersistenceUnavailableError)
    def persistence_error_handler(_: Request, __: PersistenceUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Durable advisory state is unavailable; no advisory was delivered."},
        )

    @app.exception_handler(ProviderUnavailableError)
    def provider_error_handler(_: Request, __: ProviderUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "A required live provider is unavailable; no advisory was delivered."},
        )

    @app.exception_handler(ConsentAdapterUnavailableError)
    def consent_adapter_error_handler(
        _: Request, __: ConsentAdapterUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Consent-gated data access is unavailable; no advisory was delivered."
            },
        )

    @app.exception_handler(AuthenticationError)
    def authentication_error_handler(_: Request, __: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Authentication is required for this endpoint."},
            headers={"WWW-Authenticate": "ApiKey"},
        )

    @app.exception_handler(AuthorizationError)
    def authorization_error_handler(_: Request, __: AuthorizationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "This principal is not authorised for the requested resource."},
        )

    @app.middleware("http")
    async def rate_limit_and_audit(request: Request, call_next):
        protected_path = request.url.path.startswith("/api/v1")
        if protected_path and settings.rate_limit_enabled:
            try:
                app.state.rate_limiter.check(request)
            except RateLimitExceededError:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded; retry after the configured window."},
                )

        response = await call_next(request)
        if protected_path:
            principal = getattr(request.state, "principal", None)
            outcome = "success" if response.status_code < 400 else "denied" if response.status_code in {401, 403, 429} else "error"
            try:
                app.state.audit_log.append(
                    {
                        "event_id": str(uuid4()),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "actor_subject": principal.subject if principal else "unauthenticated",
                        "actor_roles": sorted(
                            [role.value for role in principal.roles] if principal else []
                        ),
                        "authentication_method": (
                            principal.authentication_method if principal else "none"
                        ),
                        "action": f"{request.method} {request.url.path}",
                        "resource": getattr(request.state, "audit_resource", "api_route"),
                        "outcome": outcome,
                        "status_code": response.status_code,
                    }
                )
            except (RuntimeStateError, PersistenceUnavailableError):
                response.headers["X-Audit-Status"] = "unavailable"
        return response

    def service() -> AdvisoryService | ProductionAdvisoryService:
        return app.state.advisory_service

    def current_principal(request: Request) -> Principal:
        principal = app.state.authorizer.authenticate(request)
        request.state.principal = principal
        return principal

    def require_roles(*roles: Role):
        def dependency(principal: Principal = Depends(current_principal)) -> Principal:
            app.state.authorizer.require_roles(principal, frozenset(roles))
            return principal

        return dependency

    def require_farmer_assignment(principal: Principal, farmer_id: str) -> None:
        app.state.authorizer.require_farmer_assignment(principal, farmer_id)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.app_environment,
            "runtime_mode": settings.runtime_mode,
            "agent_execution": (
                "gemini_multi_agent"
                if settings.runtime_mode == "production"
                else "deterministic_fallback"
            ),
        }

    @app.get("/api/v1/agents", response_model=list[AgentDescriptor], tags=["agents"])
    def list_agents(
        _: Principal = Depends(
            require_roles(Role.FARMER, Role.EXTENSION_OFFICER, Role.SYSTEM_ADMIN)
        ),
    ) -> list[AgentDescriptor]:
        model = settings.gemini_model if settings.runtime_mode == "production" else None
        return agent_descriptors(model)

    @app.get("/api/v1/knowledge/stats", response_model=KnowledgeStats, tags=["knowledge"])
    def knowledge_stats(
        _: Principal = Depends(
            require_roles(Role.FARMER, Role.EXTENSION_OFFICER, Role.SYSTEM_ADMIN)
        ),
    ) -> KnowledgeStats:
        return service().knowledge_stats()

    @app.get(
        "/api/v1/demo/farmers",
        response_model=list[DemoFarmerSummary],
        tags=["farmers"],
    )
    def list_demo_farmers(
        _: Principal = Depends(
            require_roles(Role.FARMER, Role.EXTENSION_OFFICER, Role.SYSTEM_ADMIN)
        ),
    ) -> list[DemoFarmerSummary]:
        if settings.runtime_mode != "demo":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Synthetic farmer enumeration is disabled in production.",
            )
        return service().list_demo_farmers()

    @app.post("/api/v1/query", response_model=AdvisoryResponse, tags=["advisory"])
    def submit_query(
        request: QueryRequest,
        http_request: Request,
        principal: Principal = Depends(require_roles(Role.FARMER, Role.EXTENSION_OFFICER, Role.SYSTEM_ADMIN)),
    ) -> AdvisoryResponse:
        require_farmer_assignment(principal, request.farmer_id)
        http_request.state.audit_resource = f"farmer:{request.farmer_id}"
        try:
            return service().query(request)
        except FarmerNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown farmer ID."
            ) from error
        except ConsentNotGrantedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Advisory consent has not been granted for this farmer.",
            ) from error

    @app.get("/api/v1/farmers/{farmer_id}", tags=["farmers"])
    def get_farmer(
        farmer_id: str,
        http_request: Request,
        principal: Principal = Depends(require_roles(Role.FARMER, Role.EXTENSION_OFFICER, Role.SYSTEM_ADMIN)),
    ) -> dict[str, object]:
        require_farmer_assignment(principal, farmer_id)
        http_request.state.audit_resource = f"farmer:{farmer_id}"
        try:
            return service().get_farmer(farmer_id)
        except FarmerNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown farmer ID."
            ) from error
        except ConsentNotGrantedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Advisory consent has not been granted for this farmer.",
            ) from error

    @app.post("/api/v1/farmers/{farmer_id}/sync", tags=["farmers"])
    def sync_farmer(
        farmer_id: str,
        http_request: Request,
        _: Principal = Depends(require_roles(Role.SYSTEM_ADMIN)),
    ) -> dict[str, object]:
        if settings.runtime_mode != "production":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Farmer synchronisation is available only in the production runtime.",
            )
        http_request.state.audit_resource = f"farmer:{farmer_id}:sync"
        try:
            return service().sync_farmer(farmer_id)
        except FarmerNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown farmer ID."
            ) from error
        except ConsentNotGrantedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Advisory consent has not been granted for this farmer.",
            ) from error

    @app.post("/api/v1/memory/search", tags=["memory"])
    def search_memory(
        request: MemorySearchRequest,
        http_request: Request,
        principal: Principal = Depends(require_roles(Role.FARMER, Role.EXTENSION_OFFICER, Role.SYSTEM_ADMIN)),
    ) -> list[dict[str, object]]:
        require_farmer_assignment(principal, request.farmer_id)
        http_request.state.audit_resource = f"farmer_memory:{request.farmer_id}"
        try:
            return service().search_memory(request)
        except FarmerNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown farmer ID."
            ) from error
        except ConsentNotGrantedError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Advisory consent has not been granted for this farmer.",
            ) from error

    @app.post("/api/v1/knowledge/documents", tags=["knowledge"])
    def ingest_knowledge(
        request: KnowledgeIngestRequest,
        http_request: Request,
        _: Principal = Depends(require_roles(Role.SYSTEM_ADMIN)),
    ) -> dict[str, str]:
        if settings.runtime_mode != "production":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Knowledge ingestion is available only in the production runtime.",
            )
        http_request.state.audit_resource = f"knowledge:{request.collection}"
        document_id = service().ingest_knowledge(request)
        return {"document_id": document_id}

    @app.post(
        "/api/v1/hitl/{case_id}/decision", response_model=HITLCase, tags=["human-in-the-loop"]
    )
    def decide_hitl(
        case_id: str,
        request: HITLDecisionRequest,
        http_request: Request,
        principal: Principal = Depends(require_roles(Role.EXTENSION_OFFICER, Role.SYSTEM_ADMIN)),
    ) -> HITLCase:
        existing_case = service().get_hitl_case(case_id)
        if existing_case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown HITL case ID."
            )
        require_farmer_assignment(principal, existing_case.farmer_id)
        http_request.state.audit_resource = f"hitl_case:{case_id}"
        try:
            case = service().decide_hitl(case_id, request)
        except HITLCaseNotPendingError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This HITL case has already received a decision.",
            ) from error
        except HITLCaseSafetyBlockedError as error:
            deployment_label = (
                "local demonstrator" if settings.runtime_mode == "demo" else "current deployment"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This case has failed hard safety checks and cannot be approved in the "
                    f"{deployment_label}."
                ),
            ) from error
        if case is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown HITL case ID."
            )
        return case

    @app.get("/api/v1/hitl", response_model=list[HITLCase], tags=["human-in-the-loop"])
    def list_hitl_cases(
        http_request: Request,
        principal: Principal = Depends(require_roles(Role.EXTENSION_OFFICER, Role.SYSTEM_ADMIN)),
    ) -> list[HITLCase]:
        cases = service().list_hitl_cases()
        http_request.state.audit_resource = "hitl_queue"
        if principal.authentication_method == "development_bypass" or Role.SYSTEM_ADMIN in principal.roles:
            return cases
        allowed_farmer_ids = principal.allowed_farmer_ids or frozenset()
        return [case for case in cases if case.farmer_id in allowed_farmer_ids]

    @app.get("/api/v1/audit", tags=["security"])
    def list_audit_events(
        http_request: Request,
        limit: int = Query(default=100, ge=1, le=500),
        _: Principal = Depends(require_roles(Role.SYSTEM_ADMIN)),
    ) -> list[dict[str, object]]:
        http_request.state.audit_resource = "audit_log"
        return app.state.audit_log.list(limit)

    @app.delete(
        "/api/v1/farmers/{farmer_id}/runtime-data",
        response_model=DeletionRequest,
        tags=["privacy"],
    )
    def request_runtime_data_deletion(
        farmer_id: str,
        http_request: Request,
        principal: Principal = Depends(require_roles(Role.SYSTEM_ADMIN)),
    ) -> DeletionRequest:
        if not service().has_farmer(farmer_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown farmer ID."
            )
        http_request.state.audit_resource = f"runtime_data:{farmer_id}"
        service().purge_farmer_runtime_data(farmer_id)
        deletion_request = DeletionRequest(
            request_id=str(uuid4()),
            farmer_id=farmer_id,
            requested_by=principal.subject,
            requested_at=datetime.now(timezone.utc),
            status="pending_external_cleanup",
            locally_purged_scopes=["advisory_memory", "hitl_cases"],
            human_action_required=(
                "Confirm deletion with every configured live provider, backup system, and legal-retention owner; "
                "checked-in demo seed fixtures are immutable and outside this deletion scope."
            ),
        )
        app.state.deletion_requests.append(deletion_request.model_dump(mode="json"))
        return deletion_request

    return app


app = create_app()
