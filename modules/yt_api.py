"""
YTSPERBOT - YouTube API helper condiviso
"""

import os
import requests

YT_BASE = "https://www.googleapis.com/youtube/v3"


def yt_get(endpoint: str, params: dict) -> dict:
    params["key"] = os.getenv("YOUTUBE_API_KEY")
    response = requests.get(f"{YT_BASE}/{endpoint}", params=params, timeout=15)
    response.raise_for_status()
    return response.json()
