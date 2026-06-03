from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image
import requests


def show_result(result: dict[str, Any], open_image: bool = True) -> None:
    status = result.get("status")
    if status == "no_token":
        print("Recognition disabled: AUDD API token not configured.")
        return

    if status == "error":
        print(f"Recognition error: {result.get('error')}")
        return

    if status == "no_match":
        print("No match found for the provided audio.")
        return

    # matched
    title = result.get("title") or "(unknown)"
    artist = result.get("artist") or "(unknown)"
    album = result.get("album") or "(unknown)"

    print("")
    print(f"🎵  Song:   {title}")
    print(f"🎤  Artist: {artist}")
    print(f"💿  Album:  {album}")

    image_url = result.get("image")
    if image_url and open_image:
        try:
            resp = requests.get(image_url, timeout=10)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            img.show()
        except Exception as exc:
            print(f"Failed to load album art: {exc}")
