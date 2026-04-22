from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from database import update_user_tier, get_all_sites_for_user, deactivate_site_db
from auth import get_current_user
from tiers import TIERS
from models import TierUpdate
from scheduler import reschedule_all

router = APIRouter(prefix="/api/tiers", tags=["tiers"])

@router.get("")
def get_tiers():
    """Return all tiers as a list with the key included."""
    result = []
    for key, cfg in TIERS.items():
        result.append({**cfg, "key": key})
    return result

@router.get("/me")
def get_my_tier(current_user: Annotated[dict, Depends(get_current_user)]):
    tier_name = current_user["tier"]
    tier_cfg = TIERS.get(tier_name, TIERS["FREE"])
    
    from database import get_site_count
    used = get_site_count(current_user["id"])
    
    return {
        "tier": {**tier_cfg, "key": tier_name},
        "usage": {
            "sites_used": used,
            "sites_limit": tier_cfg["max_sites"],
            "check_interval_seconds": tier_cfg["check_interval_seconds"],
            "log_retention_days": tier_cfg["log_retention_days"]
        }
    }

@router.patch("/me")
def update_my_tier(update_data: TierUpdate, current_user: Annotated[dict, Depends(get_current_user)]):
    new_tier = update_data.tier.upper()
    if new_tier not in TIERS:
        raise HTTPException(status_code=422, detail="Invalid tier")
        
    update_user_tier(current_user["id"], new_tier)
    
    tier_cfg = TIERS[new_tier]
    all_sites = get_all_sites_for_user(current_user["id"])
    active_sites = [s for s in all_sites if s["is_active"]]
    
    deactivated = []
    if len(active_sites) > tier_cfg["max_sites"]:
        # Deactivate excess sites, newest first
        active_sites.sort(key=lambda x: x["added_at"], reverse=True)
        to_deactivate = active_sites[:len(active_sites) - tier_cfg["max_sites"]]
        for site in to_deactivate:
            deactivate_site_db(site["id"], current_user["id"])
            deactivated.append({"id": site["id"], "name": site["name"], "url": site["url"]})
            
    reschedule_all()
    
    return {
        "message": f"Successfully updated tier to {tier_cfg['name']}",
        "tier": {**tier_cfg, "key": new_tier},
        "deactivated_sites": deactivated
    }
