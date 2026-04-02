"""
YTSPERBOT - YouTube API helper condiviso
"""

import os
import requests

YT_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeQuotaExceeded(Exception):
    """Raised when the YouTube Data API v3 daily quota is exhausted (HTTP 403 quotaExceeded)."""


def yt_get(endpoint: str, params: dict) -> dict:
    params["key"] = os.getenv("YOUTUBE_API_KEY")
    response = requests.get(f"{YT_BASE}/{endpoint}", params=params, timeout=15)
    if response.status_code == 403:
        try:
            errors = response.json().get("error", {}).get("errors", [])
            reasons = {e.get("reason", "") for e in errors}
        except Exception:
            reasons = set()
        if reasons & {"quotaExceeded", "dailyLimitExceeded"}:
            raise YouTubeQuotaExceeded("YouTube API daily quota exhausted")
    response.raise_for_status()
    return response.json()
