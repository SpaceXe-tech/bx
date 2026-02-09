import os
import re

import aiofiles
import aiohttp
from PIL import Image, ImageEnhance

from youtubesearchpython.future import VideosSearch

from config import YOUTUBE_IMG_URL


def changeImageSize(maxWidth, maxHeight, image: Image.Image) -> Image.Image:
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    return image.resize((newWidth, newHeight))


def clear(text: str) -> str:
    parts = text.split(" ")
    title = ""
    for part in parts:
        if len(title) + len(part) < 60:
            title += " " + part
    return title.strip()


def _extract_video_id_from_url(value: str) -> str:
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([0-9A-Za-z_-]{11})",
        r"youtube\.com/v/([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, value)
        if m:
            return m.group(1)
    return value


def _normalize_video_input(value: str) -> tuple[str, str]:
    raw = value.strip()
    if "youtube.com" in raw or "youtu.be" in raw:
        vid = _extract_video_id_from_url(raw)
        url = raw
    else:
        if len(raw) == 12 and raw[0] == "_" and re.match(r"[0-9A-Za-z_-]{11}$", raw[1:]):
            raw = raw[1:]
        vid = raw
        url = f"https://www.youtube.com/watch?v={vid}"
    return url, vid


async def get_qthumb(videoid: str) -> str:
    try:
        _, vid = _normalize_video_input(videoid)
        return f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
    except Exception:
        return YOUTUBE_IMG_URL


async def get_thumb(videoid: str) -> str:
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    url, vid = _normalize_video_input(videoid)

    try:
        results = VideosSearch(url, limit=1)
        data = await results.next()
        result_list = data.get("result") or []
        if result_list:
            result = result_list[0]
            try:
                title = result.get("title") or ""
                title = re.sub(r"\W+", " ", title).title()
            except Exception:
                title = "Unknown Track"
            try:
                duration = result.get("duration") or "Unknown Mins"
            except Exception:
                duration = "Min"
            try:
                thumbnail = (result.get("thumbnails") or [{}])[0].get("url", "").split("?")[0]
            except Exception:
                thumbnail = YOUTUBE_IMG_URL
            try:
                views = (result.get("viewCount") or {}).get("short") or "Unknown Views"
            except Exception:
                views = "• Views"
            try:
                channel = (result.get("channel") or {}).get("name") or "Unknown Channel"
            except Exception:
                channel = "Youtube"
        else:
            thumbnail = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
            title = "Unknown Track"
            duration = "Min"
            views = "• Views"
            channel = "Youtube"

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    tmp_path = f"cache/thumb{vid}.png"
                    f = await aiofiles.open(tmp_path, mode="wb")
                    await f.write(await resp.read())
                    await f.close()
                else:
                    return YOUTUBE_IMG_URL

        youtube = Image.open(f"cache/thumb{vid}.png")
        image1 = changeImageSize(1280, 720, youtube)
        bg_bright = ImageEnhance.Brightness(image1)
        bg_logo = bg_bright.enhance(1.1)
        bg_contra = ImageEnhance.Contrast(bg_logo)
        background = changeImageSize(1280, 720, bg_contra.enhance(1.1))

        try:
            os.remove(f"cache/thumb{vid}.png")
        except Exception:
            pass

        final_path = f"cache/{vid}.png"
        background.save(final_path)
        return final_path

    except Exception as e:
        print(e)
        return YOUTUBE_IMG_URL
