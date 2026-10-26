import hashlib
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.incidents import Analysis, Incident, Postmortem, Tenant

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="src/dashboard/templates")


async def _get_tenant(
    db: AsyncSession,
    api_key: str | None,
    cookie: str | None,
) -> Tenant | None:
    key = api_key or cookie
    if not key:
        return None
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    result = await db.execute(select(Tenant).where(Tenant.api_key_hash == key_hash))
    return result.scalar_one_or_none()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": error})


@router.post("/login")
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    api_key = form.get("api_key", "")
    tenant = await _get_tenant(db, api_key, None)
    if not tenant:
        return templates.TemplateResponse(
            request=request, name="login.html", context={"error": "Invalid API key"}, status_code=401
        )
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("rootsignal_api_key", api_key, httponly=True, max_age=86400 * 30)
    return response


@router.get("", response_class=HTMLResponse)
async def incident_list(
    request: Request,
    api_key: str | None = Query(default=None),
    rootsignal_api_key: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _get_tenant(db, api_key, rootsignal_api_key)
    if not tenant:
        return RedirectResponse(url="/dashboard/login")

    result = await db.execute(
        select(Incident).where(Incident.tenant_id == tenant.id)
        .order_by(Incident.started_at.desc()).limit(20)
    )
    incidents = result.scalars().all()

    rows = []
    for inc in incidents:
        analysis = (await db.execute(
            select(Analysis).where(Analysis.incident_id == inc.id)
        )).scalar_one_or_none()
        rows.append({"incident": inc, "analysis": analysis})

    return templates.TemplateResponse(request=request, name="incidents.html", context={"incidents": rows})


@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
async def incident_detail(
    incident_id: uuid.UUID,
    request: Request,
    api_key: str | None = Query(default=None),
    rootsignal_api_key: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _get_tenant(db, api_key, rootsignal_api_key)
    if not tenant:
        return RedirectResponse(url="/dashboard/login")

    incident = await db.get(Incident, incident_id)
    if not incident or incident.tenant_id != tenant.id:
        raise HTTPException(status_code=404)

    analysis = (await db.execute(
        select(Analysis).where(Analysis.incident_id == incident_id)
    )).scalar_one_or_none()

    postmortem = (await db.execute(
        select(Postmortem).where(Postmortem.incident_id == incident_id)
    )).scalar_one_or_none()

    return templates.TemplateResponse(request=request, name="incident_detail.html", context={
        "incident": incident,
        "analysis": analysis,
        "postmortem": postmortem,
    })
