from typing import TypedDict, Dict

class TierConfig(TypedDict):
    name: str
    price_label: str
    max_sites: int
    check_interval_seconds: int
    log_retention_days: int

TIERS: Dict[str, TierConfig] = {
    "FREE": {
        "name": "Free",
        "price_label": "$0 / month",
        "max_sites": 1,
        "check_interval_seconds": 300,
        "log_retention_days": 7
    },
    "PRO": {
        "name": "Pro",
        "price_label": "Contact us",
        "max_sites": 10,
        "check_interval_seconds": 60,
        "log_retention_days": 30
    },
    "ENTERPRISE": {
        "name": "Enterprise",
        "price_label": "Contact us",
        "max_sites": 999999,
        "check_interval_seconds": 10,
        "log_retention_days": 0
    }
}
