from fastapi import FastAPI

from src.db.session import init_db
from src.models import incidents as _models  # noqa: F401 — registers all models with Base
from src.webhook.pagerduty import router as pagerduty_router
from src.webhook.opsgenie import router as opsgenie_router
from src.webhook.grafana import router as grafana_router
from src.routes.incidents import router as incidents_router
from src.routes.tenants import router as tenants_router
from src.webhook.gitlab import router as gitlab_router
from src.dashboard.routes import router as dashboard_router

app = FastAPI(title="RootSignal", version="0.1.0")


@app.on_event("startup")
async def startup():
    await init_db()


app.include_router(pagerduty_router, prefix="/webhook")
app.include_router(opsgenie_router, prefix="/webhook")
app.include_router(grafana_router, prefix="/webhook")
app.include_router(gitlab_router, prefix="/webhook")
app.include_router(incidents_router)
app.include_router(tenants_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
