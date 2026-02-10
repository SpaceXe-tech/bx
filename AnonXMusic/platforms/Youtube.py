import os
import re
import json
import glob
import random
import yt_dlp
import time
import asyncio
import aiofiles
import httpx
from typing import Union, Tuple, Optional, Dict, Any

from config import API_URL
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.future import VideosSearch, Playlist
from AnonXMusic.utils.database import is_on_off
from AnonXMusic.utils.formatters import time_to_seconds
from .. import LOGGER

logger = LOGGER(__name__)

TIMEOUT = 30
DOWNLOAD_TIMEOUT = 60
MAX_SIZE_MB = 500
FRAGMENTS = 42
CHUNK_SIZE = 8 * 1024 * 1024

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


def _api_endpoint() -> Optional[str]:
    if not API_URL:
        return None
    return API_URL.rstrip("/")


def _origin_referer_headers() -> Dict[str, str]:
    base = (API_URL or "").rstrip("/") + "/"
    h = dict(BROWSER_HEADERS)
    if base.startswith("http"):
        h["Origin"] = base.rstrip("/")
        h["Referer"] = base
    return h


def cookie_txt_file():
    folder_path = os.path.join(os.getcwd(), "cookies")
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in cookies folder.")
    return random.choice(txt_files)


async def download_with_api(video_id: str, download_mode: str = "audio") -> Optional[str]:
    endpoint = _api_endpoint()
    if not endpoint:
        return None

    if download_mode == "audio":
        fmt = "m4a"
        ext = "m4a"
    else:
        fmt = "360"
        ext = "mp4"

    video_url = f"https://youtu.be/{video_id}"
    file_path = os.path.join("downloads", f"{video_id}.{ext}")

    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path

        params = {"url": video_url, "format": fmt}
        headers = _origin_referer_headers()
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
        timeout = httpx.Timeout(TIMEOUT, read=DOWNLOAD_TIMEOUT)

        async with httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
        ) as client:
            r = await client.get(endpoint, params=params)
            if r.status_code != 200:
                return None

            try:
                data = r.json()
            except Exception:
                try:
                    data = json.loads(r.text)
                except Exception:
                    return None

            if str(data.get("status", "")).lower() != "success":
                return None

            download_url = data.get("download_url")
            if not download_url:
                return None

            head = await client.head(
                download_url,
                headers={"Accept-Encoding": "identity"},
            )
            if head.status_code not in (200, 206):
                pass

            cl = head.headers.get("Content-Length")
            if cl:
                try:
                    size_mb = int(cl) / (1024 * 1024)
                    if size_mb > MAX_SIZE_MB:
                        return None
                except Exception:
                    pass

            os.makedirs("downloads", exist_ok=True)
            tmp = file_path + ".part"

            async with client.stream(
                "GET",
                download_url,
                headers={"Accept-Encoding": "identity"},
            ) as resp:
                if resp.status_code not in (200, 206):
                    return None
                async with aiofiles.open(tmp, "wb") as f:
                    async for chunk in resp.aiter_bytes(CHUNK_SIZE):
                        if chunk:
                            await f.write(chunk)

            if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                os.replace(tmp, file_path)

        if os.path.getsize(file_path) > 0:
            logger.info(f"API success: {video_id} -> {ext}")
            return file_path
        return None
    except Exception:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        return None


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.base_url = self.base
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.listbase = "https://youtube.com/playlist?list="

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        link = (link or "").strip().strip("<>")
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()
        elif isinstance(videoid, bool) and videoid:
            if re.fullmatch(r"[0-9A-Za-z_-]{11}", link):
                link = self.base_url + link
        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    def _extract_raw_video_id(self, value: str) -> str:
        value = (value or "").strip().strip("<>")
        if re.fullmatch(r"[0-9A-Za-z_-]{11}", value):
            return value
        if "v=" in value:
            return value.split("v=")[-1].split("&")[0]
        if "youtu.be" in value or "youtube.com" in value:
            return value.split("/")[-1].split("?")[0]
        return value

    def extract_video_id(self, value: str) -> str:
        raw = self._extract_raw_video_id(value)
        if re.fullmatch(r"[0-9A-Za-z_-]{11}", raw):
            return raw
        raise ValueError(f"Invalid YouTube link or video id: {value}")

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        link = self._prepare_link(link, videoid)
        return bool(re.search(self.regex, link or ""))

    async def url(self, message_1: Message) -> Optional[str]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        if text:
                            return text[entity.offset : entity.offset + entity.length]
                    elif entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def _get_info(self, link: str) -> Dict[str, Any]:
        try:
            results = VideosSearch(link, limit=1)
            result_data = await asyncio.wait_for(results.next(), timeout=TIMEOUT)
            return result_data["result"][0] if result_data["result"] else {}
        except Exception:
            return {}

    async def info(
        self, link: str, videoid: Union[bool, str] = None
    ) -> Tuple[str, str, int, str, str]:
        link = self._prepare_link(link, videoid)
        result = await self._get_info(link)
        if not result:
            return "", "", 0, "", ""
        title = result.get("title", "")
        duration_min = result.get("duration", "")
        thumbnail = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        vidid = result.get("id", "")
        duration_sec = 0
        if duration_min and duration_min != "None":
            try:
                duration_sec = int(time_to_seconds(duration_min))
            except Exception:
                pass
        return title, duration_min, duration_sec, thumbnail, vidid

    async def details(
        self, link: str, videoid: Union[bool, str] = None
    ) -> Tuple[str, str, int, str, str]:
        title, duration_min, duration_sec, thumbnail, vidid = await self.info(
            link, videoid=videoid
        )
        if not title:
            raise ValueError("No details found")
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._prepare_link(link, videoid)
        result = await self._get_info(link)
        return result.get("title", "")

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._prepare_link(link, videoid)
        result = await self._get_info(link)
        return result.get("duration", "")

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._prepare_link(link, videoid)
        result = await self._get_info(link)
        thumbnails = result.get("thumbnails", [])
        return thumbnails[0].get("url", "").split("?")[0] if thumbnails else ""

    async def video(self, link: str, videoid: Union[bool, str] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies",
                    cookie_txt_file(),
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    link,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=TIMEOUT,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
            if stdout:
                url = stdout.decode().split("\n")[0].strip()
                return (1, url) if url else (0, "No URL found")
            else:
                return 0, stderr.decode()
        except Exception:
            return 0, "Timeout or error occurred"

    async def slider(
        self, link: str, query_type: int, videoid: Union[bool, str] = None
    ) -> Tuple[str, str, str, str]:
        link = self._prepare_link(link, videoid)
        try:
            results = VideosSearch(link, limit=min(query_type + 1, 10))
            result_data = await asyncio.wait_for(results.next(), timeout=TIMEOUT)
            result_list = result_data.get("result", [])
            if query_type < len(result_list):
                item = result_list[query_type]
                return (
                    item.get("title", ""),
                    item.get("duration", ""),
                    item.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
                    item.get("id", ""),
                )
        except Exception:
            pass
        return "", "", "", ""

    async def playlist(
        self,
        link: str,
        limit: int,
        user_id: int,
        videoid: Union[bool, str] = None,
    ) -> list:
        link = (link or "").strip()
        if videoid:
            link = self.listbase + str(link).strip()
        if "&" in link:
            link = link.split("&", 1)[0]
        try:
            def get_playlist_ids():
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": True,
                    "skip_download": True,
                    "cookiefile": cookie_txt_file(),
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    if not info:
                        return []
                    entries = info.get("entries", []) or []
                    ids = []
                    for entry in entries[:limit]:
                        vid = entry.get("id")
                        if vid:
                            ids.append(vid)
                    return ids

            loop = asyncio.get_running_loop()
            ids = await asyncio.wait_for(
                loop.run_in_executor(None, get_playlist_ids),
                timeout=TIMEOUT,
            )
            return ids
        except Exception as e:
            logger.error(f"Playlist parse error for {link}: {e}")
            return []

    async def track(self, query: str) -> Tuple[Dict[str, Any], str]:
        query = (query or "").strip()
        is_yt_link = bool(re.search(self.regex, query))
        if is_yt_link:
            prepared = self._prepare_link(query, None)
            title, duration_min, duration_sec, thumb, vidid = await self.info(prepared)
        else:
            title, duration_min, duration_sec, thumb, vidid = await self.info(query)
        if not title:
            return {}, ""
        if not vidid:
            try:
                vidid = self.extract_video_id(prepared if is_yt_link else query)
            except Exception:
                pass
        if vidid:
            link = f"https://youtu.be/{vidid}"
        else:
            link = prepared if is_yt_link else query
        details = {
            "title": title,
            "duration_min": duration_min,
            "duration_sec": duration_sec,
            "thumb": thumb or "",
            "link": link,
        }
        return details, vidid

    async def download(
        self,
        link: str,
        mystic: Any,
        video: bool = False,
        videoid: bool = False,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Tuple[Optional[str], bool]:
        link = self._prepare_link(link, videoid)
        try:
            video_id = self.extract_video_id(link)
        except ValueError:
            return None, False

        os.makedirs("downloads", exist_ok=True)

        def ytdlp_audio():
            try:
                opts = {
                    "format": "bestaudio/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "no_warnings": True,
                    "concurrent_fragment_downloads": FRAGMENTS,
                    "http_headers": BROWSER_HEADERS,
                }
                ydl = yt_dlp.YoutubeDL(opts)
                info = ydl.extract_info(link, download=False)
                if not info:
                    return None
                file_path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return file_path
                ydl.download([link])
                return (
                    file_path
                    if os.path.exists(file_path)
                    and os.path.getsize(file_path) > 0
                    else None
                )
            except Exception:
                return None

        def ytdlp_video():
            try:
                opts = {
                    "format": "best[height<=720][ext=mp4]/best[ext=mp4]/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "no_warnings": True,
                    "merge_output_format": "mp4",
                    "concurrent_fragment_downloads": FRAGMENTS,
                    "http_headers": BROWSER_HEADERS,
                }
                ydl = yt_dlp.YoutubeDL(opts)
                info = ydl.extract_info(link, download=False)
                if not info:
                    return None
                file_path = os.path.join("downloads", f"{info['id']}.mp4")
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return file_path
                ydl.download([link])
                return (
                    file_path
                    if os.path.exists(file_path)
                    and os.path.getsize(file_path) > 0
                    else None
                )
            except Exception:
                return None

        def ytdlp_song_video():
            if not format_id or not title:
                return None
            try:
                opts = {
                    "format": f"{format_id}+140",
                    "outtmpl": f"downloads/{title}",
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "no_warnings": True,
                    "merge_output_format": "mp4",
                    "concurrent_fragment_downloads": FRAGMENTS,
                    "http_headers": BROWSER_HEADERS,
                }
                ydl = yt_dlp.YoutubeDL(opts)
                ydl.download([link])
                result_path = f"downloads/{title}.mp4"
                return (
                    result_path
                    if os.path.exists(result_path)
                    and os.path.getsize(result_path) > 0
                    else None
                )
            except Exception:
                return None

        def ytdlp_song_audio():
            if not format_id or not title:
                return None
            try:
                opts = {
                    "format": format_id,
                    "outtmpl": f"downloads/{title}.%(ext)s",
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "no_warnings": True,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                    "concurrent_fragment_downloads": FRAGMENTS,
                    "http_headers": BROWSER_HEADERS,
                }
                ydl = yt_dlp.YoutubeDL(opts)
                ydl.download([link])
                result_path = f"downloads/{title}.mp3"
                return (
                    result_path
                    if os.path.exists(result_path)
                    and os.path.getsize(result_path) > 0
                    else None
                )
            except Exception:
                return None

        try:
            loop = asyncio.get_running_loop()

            if songvideo:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, ytdlp_song_video),
                    timeout=DOWNLOAD_TIMEOUT,
                )
                return result, result is not None

            if songaudio:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, ytdlp_song_audio),
                    timeout=DOWNLOAD_TIMEOUT,
                )
                return result, result is not None

            if video:
                api_path = await download_with_api(video_id, "video")
                if api_path:
                    return api_path, True
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, ytdlp_video),
                    timeout=DOWNLOAD_TIMEOUT,
                )
                return result, result is not None

            api_path = await download_with_api(video_id, "audio")
            if api_path:
                return api_path, True
            result = await asyncio.wait_for(
                loop.run_in_executor(None, ytdlp_audio),
                timeout=DOWNLOAD_TIMEOUT,
            )
            return result, result is not None
    
        except asyncio.TimeoutError:
            logger.error(f"Download timeout: {video_id}")
            return None, False

        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return None, False
