from fastapi import FastAPI
from app.core.middleware import JWTAuthMiddleware
from app.modules.auth.auth_router import router as auth_router
from app.modules.training.training_router import router as training_router
from app.modules.checklist.checklist_router import router as checklist_router

app = FastAPI(title="SST Backend")
#app.add_middleware(
#    JWTAuthMiddleware,
#    excluded_paths={"/auth/login", "/auth/verify-otp", "/auth/refresh", "/health", "/docs", "/openapi.json"},
#)

app.include_router(auth_router)
app.include_router(training_router)
app.include_router(checklist_router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "sst-backend"}
