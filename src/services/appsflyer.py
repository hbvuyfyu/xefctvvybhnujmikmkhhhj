import requests
import random
import logging
import time
from typing import Optional, Dict, Tuple

from src.config import SDK_VERSION

logger = logging.getLogger(__name__)

AF_API_URL = "https://api2.appsflyer.com/inappevent/{package}"


def _build_proxy(proxy: Optional[Dict]) -> Optional[Dict]:
    if not proxy:
        return None
    host = proxy.get("host", "")
    port = proxy.get("port", "")
    ptype = proxy.get("proxy_type", "http").lower()
    user = proxy.get("username", "")
    password = proxy.get("password", "")
    if user and password:
        auth = f"{user}:{password}@"
    else:
        auth = ""
    proxy_url = f"{ptype}://{auth}{host}:{port}"
    return {"http": proxy_url, "https": proxy_url}


def send_af(
    pkg: str,
    dev_key: str,
    gaid: str,
    af_uid: str,
    event_name: str,
    revenue: float = None,
    proxy: Optional[Dict] = None,
    platform: str = "android",
    idfa: str = None,
    idfv: str = None,
    level: int = None,
) -> Tuple[int, str]:
    url = AF_API_URL.format(package=pkg)

    if platform == "ios":
        advertising_id = idfa or gaid
        advertising_id_type = "idfa"
    else:
        advertising_id = gaid
        advertising_id_type = "advertising_id"

    headers = {
        "authentication": dev_key,
        "Content-Type": "application/json",
        "User-Agent": f"AppsFlyer-Android-SDK/{SDK_VERSION} (Linux; Android 14; Build/UP1A.231005.007)",
    }

    event_value: Dict = {}
    if revenue is not None:
        event_value["af_revenue"] = revenue
        event_value["af_currency"] = "USD"
        event_value["af_content_type"] = "purchase"
    if level is not None:
        event_value["af_level"] = level

    payload = {
        "appsflyer_id": af_uid,
        "customer_user_id": af_uid,
        "eventName": event_name,
        "eventValue": event_value,
        "eventTime": time.strftime("%Y-%m-%d %H:%M:%S.000", time.localtime()),
        "eventCurrency": "USD",
        advertising_id_type: advertising_id,
        "ip": f"{random.randint(1, 254)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}",
        "bundleIdentifier": pkg,
        "timeZone": "Asia/Riyadh",
    }

    try:
        proxies = _build_proxy(proxy)
        r = requests.post(url, json=payload, headers=headers, timeout=30, proxies=proxies)
        logger.info(f"[AF] {pkg} | {event_name} | status={r.status_code}")
        return r.status_code, r.text[:500]
    except Exception as e:
        logger.error(f"[AF] Exception: {e}")
        return 500, str(e)
