import os
import uuid
from datetime import datetime, timezone
from typing import Annotated
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, get_sites, get_all_sites_for_user, get_logs, add_site_db, delete_site_db, get_site_count, reactivate_site_db
from models import SiteIn
from ws_manager import manager
from scheduler import start_scheduler, shutdown_scheduler, check_sites_for_interval
from checker import check_site
from auth import get_current_user, decode_access_token, get_user_by_id
from tiers import TIERS
from routers.auth import router as auth_router
from routers.tiers import router as tiers_router

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tiers_router)

@app.get("/api/sites")
def api_get_sites(current_user: Annotated[dict, Depends(get_current_user)]):
    return get_sites(current_user["id"])

@app.get("/api/sites/all")
def api_get_all_sites(current_user: Annotated[dict, Depends(get_current_user)]):
    return get_all_sites_for_user(current_user["id"])

@app.post("/api/sites")
async def api_add_site(site: SiteIn, current_user: Annotated[dict, Depends(get_current_user)]):
    tier_cfg = TIERS.get(current_user["tier"], TIERS["FREE"])
    count = get_site_count(current_user["id"])
    
    if count >= tier_cfg["max_sites"]:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Site limit reached",
                "tier": current_user["tier"],
                "limit": tier_cfg["max_sites"],
                "upgrade_hint": True
            }
        )

    site_id = str(uuid.uuid4())
    added_at = datetime.now(timezone.utc).isoformat()
    add_site_db(site_id, site.name, site.url, added_at, current_user["id"])
    
    new_site = next((s for s in get_sites(current_user["id"]) if s["id"] == site_id), None)
    if new_site:
        await check_site(new_site, current_user["id"])
        
    return {"id": site_id}

@app.delete("/api/sites/{site_id}")
def api_delete_site(site_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    site = next((s for s in get_all_sites_for_user(current_user["id"]) if s["id"] == site_id), None)
    if not site:
        raise HTTPException(status_code=403, detail="Site not found or not owned by user")
    
    delete_site_db(site_id, current_user["id"])
    return {"deleted": site_id}

@app.post("/api/sites/{site_id}/reactivate")
async def api_reactivate_site(site_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    tier_cfg = TIERS.get(current_user["tier"], TIERS["FREE"])
    count = get_site_count(current_user["id"])
    
    if count >= tier_cfg["max_sites"]:
        raise HTTPException(status_code=403, detail="Site limit reached. Cannot reactivate.")
        
    site = next((s for s in get_all_sites_for_user(current_user["id"]) if s["id"] == site_id), None)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
        
    reactivate_site_db(site_id, current_user["id"])
    new_site = next((s for s in get_sites(current_user["id"]) if s["id"] == site_id), None)
    if new_site:
        await check_site(new_site, current_user["id"])
        
    return {"status": "ok", "site": new_site}

@app.get("/api/logs")
def api_get_logs(current_user: Annotated[dict, Depends(get_current_user)], limit: int = 100):
    return get_logs(current_user["id"], limit)

@app.post("/api/check-now")
async def api_check_now(current_user: Annotated[dict, Depends(get_current_user)]):
    all_user_sites = get_sites(current_user["id"])
    import asyncio
    if all_user_sites:
        tasks = [check_site(s, current_user["id"]) for s in all_user_sites]
        await asyncio.gather(*tasks, return_exceptions=True)
    return {"status": "ok"}

@app.post("/api/sites/{site_id}/check")
async def api_check_single(site_id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    sites = get_sites(current_user["id"])
    target = next((s for s in sites if s["id"] == site_id), None)
    if target:
        await check_site(target, current_user["id"])
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Site not found")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    if not token:
        await websocket.close(code=4001)
        return
        
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=4001)
        return
        
    user_id = payload["sub"]
    if not get_user_by_id(user_id):
        await websocket.close(code=4001)
        return
        
    await manager.connect(websocket, user_id)
    try:
        sites = get_sites(user_id)
        await websocket.send_json({"type": "init", "sites": sites})
        while True:
            data = await websocket.receive_text()
            pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
