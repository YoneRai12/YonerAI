from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ora_core.api.routes.messages import router as messages_router
from ora_core.api.routes.runs import router as runs_router
from ora_core.api.routes.auth import router as auth_router
from ora_core.api.routes.stats import router as stats_router

def create_app():
    app = FastAPI(title="ORA Core", version="0.1")

    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request schema is invalid. Please follow the Canonical Schema.",
                "details": exc.errors(),
                "manual": {
                    "example": {
                        "conversation_id": None,
                        "user_identity": {"provider": "web", "id": "local-user-1", "display_name": "YoneRai12"},
                        "content": "Hello",
                        "attachments": [],
                        "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
                    },
                    "notes": [
                        "conversation_id can be null (Core creates new).",
                        "idempotency_key must be stable per retry (UUID v4 recommended).",
                        "attachments must be typed objects, not just strings."
                    ]
                }
            },
        )
    
    app.add_middleware(
        CORSMiddleware,

        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(messages_router, prefix="/v1")
    app.include_router(runs_router, prefix="/v1")
    app.include_router(auth_router, prefix="/v1/auth")
    app.include_router(stats_router, prefix="/v1")
    
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ora_core.main:app", host="0.0.0.0", port=8001, reload=True)
