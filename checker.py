import httpx
import time
from datetime import datetime, timezone
from typing import Dict, Any
from database import upsert_site_status, insert_log, get_user_by_id
from ws_manager import manager
from emailer import send_alert_email

async def check_site(site: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    url = site["url"]
    start_time = time.time()
    status = "DOWN"
    http_code = None
    error_msg = None
    
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"})
            http_code = response.status_code
            if http_code < 400:
                status = "UP"
            else:
                error_msg = f"HTTP {http_code}"
    except httpx.TimeoutException:
        error_msg = "Timeout"
    except Exception as e:
        error_msg = str(e)
        
    response_time = int((time.time() - start_time) * 1000)
    checked_at = datetime.now(timezone.utc).isoformat()
    
    prev_status = site.get("status", "UNKNOWN")
    msg_type = "alert" if prev_status != "UNKNOWN" and prev_status != status else "check"
    
    upsert_site_status(site["id"], status, response_time, checked_at)
    insert_log(site["id"], site["name"], url, status, response_time, http_code, error_msg, checked_at, user_id)
    
    result = {
        "type": msg_type,
        "site_id": site["id"],
        "name": site["name"],
        "url": url,
        "status": status,
        "response_time": response_time,
        "http_code": http_code,
        "error": error_msg,
        "last_checked": checked_at
    }
    
    if msg_type == "alert":
        result["prev_status"] = prev_status
        # Send email notification on status change
        user = get_user_by_id(user_id)
        if user:
            send_alert_email(
                to_email=user["email"],
                site_name=site["name"],
                site_url=url,
                status=status,
                error_msg=error_msg,
                response_time=response_time
            )
        
    await manager.broadcast_to_user(user_id, result)
    return result
