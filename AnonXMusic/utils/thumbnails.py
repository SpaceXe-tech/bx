import os
import re
from collections import Counter

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.future import VideosSearch

from config import YOUTUBE_IMG_URL

FONT_TITLE_PATH = "AnonXMusic/assets/font.ttf"
FONT_INFO_PATH = "AnonXMusic/assets/font2.ttf"

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

class Thumbnail:
    def __init__(self):
        self.size = (1280, 720)
        try:
            self.font_title = ImageFont.truetype(FONT_TITLE_PATH, 55)
            self.font_info = ImageFont.truetype(FONT_INFO_PATH, 40)
        except Exception:
            self.font_title = ImageFont.load_default()
            self.font_info = ImageFont.load_default()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(output_path, "wb") as f:
                        await f.write(await resp.read())
        return output_path

    def _truncate_text(self, draw, text, font, max_width):
        try:
            get_width = lambda t: draw.textlength(t, font=font)
        except AttributeError:
            get_width = lambda t: draw.textsize(t, font=font)[0]
            
        if get_width(text) <= max_width:
            return text
            
        while text and get_width(text + "..") > max_width:
            text = text[:-1]
        return text + ".."

    def _get_dominant_colors(self, image):
        img = image.copy().resize((50, 50)).convert("RGB")
        return Counter(list(img.getdata())).most_common(1)[0][0]

    async def generate(self, videoid: str) -> str:
        try:
            os.makedirs("cache", exist_ok=True)
            url, vid = _normalize_video_input(videoid)
            output = f"cache/{vid}.png"
            temp = f"cache/temp_{vid}.jpg"

            if os.path.exists(output):
                return output

            results = VideosSearch(url, limit=1)
            data = await results.next()
            result_list = data.get("result") or []
            
            if result_list:
                result = result_list[0]
                title = result.get("title") or "Unknown Track"
                title = re.sub(r"\W+", " ", title).title()
                views = (result.get("viewCount") or {}).get("short") or "Unknown Views"
                channel = (result.get("channel") or {}).get("name") or "Unknown Channel"
                thumbnail_url = (result.get("thumbnails") or [{}])[0].get("url", "").split("?")[0]
            else:
                title = "Unknown Track"
                views = "• Views"
                channel = "Youtube"
                thumbnail_url = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"

            if not thumbnail_url:
                thumbnail_url = YOUTUBE_IMG_URL

            await self.save_thumb(temp, thumbnail_url)
            
            if not os.path.exists(temp):
                return YOUTUBE_IMG_URL

            raw_cover = Image.open(temp).convert("RGBA")
            
            bg = ImageOps.fit(raw_cover, self.size, method=Image.Resampling.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(40))
            bg = ImageEnhance.Brightness(bg).enhance(0.5)
            bg = ImageEnhance.Contrast(bg).enhance(1.6)
            bg = ImageEnhance.Color(bg).enhance(2.0)

            portrait_size = (540, 500)
            portrait = ImageOps.fit(raw_cover, portrait_size, method=Image.Resampling.LANCZOS)
            portrait = ImageEnhance.Contrast(portrait).enhance(1.2)
            portrait = ImageEnhance.Color(portrait).enhance(1.5)
            
            mask = Image.new("L", portrait_size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, *portrait_size), 30, fill=255)
            portrait.putalpha(mask)

            px, py = (self.size[0] - portrait_size[0]) // 2, 70
            bg.paste(portrait, (px, py), portrait)

            draw = ImageDraw.Draw(bg)
            
            tx_top = py + portrait_size[1] + 20 
            safe_w = portrait_size[0] - 20

            title_text = self._truncate_text(draw, title.upper(), self.font_title, safe_w)
            info = f"{channel}  •  {views}"
            info_text = self._truncate_text(draw, info, self.font_info, safe_w)

            draw.text((self.size[0] // 2, tx_top), title_text, font=self.font_title, fill=(255, 255, 255), anchor="ma")
            draw.text((self.size[0] // 2, tx_top + 60), info_text, font=self.font_info, fill=(255, 255, 255, 210), anchor="ma")

            dominant = self._get_dominant_colors(raw_cover)
            bx, bt, bb = self.size[0] - 80, py + 20, py + portrait_size[1] - 20
            draw.rounded_rectangle((bx - 5, bt, bx + 5, bb), 5, fill=(255, 255, 255, 40))
            
            prog_h = int((bb - bt) * 0.7)
            draw.rounded_rectangle((bx - 5, bb - prog_h, bx + 5, bb), 5, fill=dominant)

            bg.save(output, "PNG")
            if os.path.exists(temp):
                os.remove(temp)
            return output

        except Exception:
            return YOUTUBE_IMG_URL

async def get_thumb(videoid: str) -> str:
    thumb = Thumbnail()
    return await thumb.generate(videoid)

async def get_qthumb(videoid: str) -> str:
    try:
        _, vid = _normalize_video_input(videoid)
        return f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
    except Exception:
        return YOUTUBE_IMG_URL
