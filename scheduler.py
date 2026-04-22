import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from checker import check_site
from tiers import TIERS

scheduler = AsyncIOScheduler()

async def check_sites_for_interval(interval_seconds: int):
    from database import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT s.*, u.tier
        FROM sites s
        JOIN users u ON s.user_id = u.id
        WHERE s.is_active = 1
    """)
    rows = c.fetchall()
    conn.close()
    
    tasks = []
    for row in rows:
        site = dict(row)
        tier_cfg = TIERS.get(site["tier"], TIERS["FREE"])
        if tier_cfg["check_interval_seconds"] == interval_seconds:
            tasks.append(check_site(site, site["user_id"]))
            
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

def reschedule_all():
    global scheduler
    scheduler.remove_all_jobs()
    intervals = set(cfg["check_interval_seconds"] for cfg in TIERS.values())
    for interval in intervals:
        scheduler.add_job(check_sites_for_interval, 'interval', seconds=interval, args=[interval])
    scheduler.add_job(cleanup_old_logs, 'cron', hour=0, minute=0)

def cleanup_old_logs():
    from database import get_connection, delete_old_logs
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, tier FROM users")
    users = c.fetchall()
    conn.close()
    
    for row in users:
        tier_cfg = TIERS.get(row["tier"], TIERS["FREE"])
        retention = tier_cfg["log_retention_days"]
        if retention > 0:
            delete_old_logs(row["id"], retention)

def start_scheduler():
    reschedule_all()
    scheduler.start()

def shutdown_scheduler():
    scheduler.shutdown()
