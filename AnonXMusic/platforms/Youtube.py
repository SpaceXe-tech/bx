import asyncio
import os
import re
import json
from typing import Union, Tuple, List, Dict, Optional
import glob
import logging
from functools import lru_cache
from cachetools import TTLCache
import aiohttp
import time
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from AnonXMusic.utils.database import is_on_off
from AnonXMusic.utils.formatters import time_to_seconds


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

metadata_cache = TTLCache(maxsize=1000, ttl=3600)
file_size_cache = TTLCache(maxsize=100, ttl=600)

from config import API_URL1, API_URL2

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self.regex = re.compile(r"(?:youtube\.com|youtu\.be)")
        self.video_id_pattern = re.compile(r"(?:v=|youtu\.be/|youtube\.com/(?:embed/|v/|watch\?v=))([0-9A-Za-z_-]{11})")
        self._mp3_api_url = config.API_URL1  # Audio API (m4a)
        self._video_api_url = config.API_URL2  # Video API (480p)
        self._session = None
        self._cookie_files = self._load_cookie_files()
        self._current_cookie_index = 0
        self._ytdl_opts = {
            "quiet": True,
            "cookiefile": self._get_current_cookie_file(),
            "geo_bypass": True,
            "nocheckcertificate": True,
            "no_warnings": True,
        }

    def _load_cookie_files(self) -> List[str]:
        folder_path = f"{os.getcwd()}/cookies"
        filename = f"{os.getcwd()}/cookies/logs.csv"
        txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
        if not txt_files:
            raise FileNotFoundError("No .txt files found in the specified folder.")
        with open(filename, 'a') as file:
            for txt_file in txt_files:
                file.write(f'Loaded Cookie File: {txt_file}\n')
        return txt_files

    def _get_current_cookie_file(self) -> str:
        return self._cookie_files[self._current_cookie_index]

    def _cycle_cookie_file(self):
        self._current_cookie_index = (self._current_cookie_index + 1) % len(self._cookie_files)
        self._ytdl_opts["cookiefile"] = self._get_current_cookie_file()
        logger.info(f"Switched to cookie file: {self._ytdl_opts['cookiefile']}")

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session and not self._session.closed:
            await self._session.close()

    @lru_cache(maxsize=100)
    def _clean_url(self, link: str) -> str:
        if "&" in link:
            link = link.split("&")[0]
        return link

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(self.regex.search(link))

    async def url(self, message_1: Message) -> Optional[str]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset:entity.offset + entity.length]
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    @lru_cache(maxsize=500)
    async def _fetch_video_metadata(self, link: str) -> Dict:
        link = self._clean_url(link)
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            duration_min = result["duration"]
            duration_sec = 0 if duration_min == "None" else int(time_to_seconds(duration_min))
            return {
                "title": result["title"],
                "duration_min": duration_min,
                "duration_sec": duration_sec,
                "thumbnail": result["thumbnails"][0]["url"].split("?")[0],
                "vidid": result["id"],
                "link": result["link"]
            }
        except Exception as e:
            logger.error(f"Failed to fetch metadata for {link}: {str(e)}")
            return {}

    async def details(self, link: str, videoid: Union[bool, str] = None) -> Tuple[str, str, int, str, str]:
        if videoid:
            link = self.base + link
        metadata = await self._fetch_video_metadata(link)
        if not metadata:
            return "", "", 0, "", ""
        return (
            metadata["title"],
            metadata["duration_min"],
            metadata["duration_sec"],
            metadata["thumbnail"],
            metadata["vidid"]
        )

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        metadata = await self._fetch_video_metadata(link)
        return metadata.get("title", "")

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        metadata = await self._fetch_video_metadata(link)
        return metadata.get("duration_min", "")

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        metadata = await self._fetch_video_metadata(link)
        return metadata.get("thumbnail", "")

    async def video(self, link: str, videoid: Union[bool, str] = None) -> Tuple[int, str]:
        if videoid:
            link = self.base + link
        link = self._clean_url(link)
        for _ in range(len(self._cookie_files)):
            ydl = yt_dlp.YoutubeDL(self._ytdl_opts)
            try:
                info = ydl.extract_info(link, download=False)
                for format in info["formats"]:
                    if "height" in format and format["height"] <= 720 and format["width"] <= 1280:
                        return 1, format["url"]
                return 0, "No suitable format found"
            except yt_dlp.utils.DownloadError as e:
                if "unavailable" in str(e).lower():
                    logger.warning(f"Video unavailable with current cookie: {str(e)}")
                    self._cycle_cookie_file()
                    continue
                logger.error(f"Error fetching video stream: {str(e)}")
                return 0, str(e)
            except Exception as e:
                logger.error(f"Unexpected error fetching video stream: {str(e)}")
                return 0, str(e)
        return 0, "Video unavailable after trying all cookies"

    async def playlist(self, link: str, limit: int, user_id: int, videoid: Union[bool, str] = None) -> List[str]:
        if videoid:
            link = self.listbase + link
        link = self._clean_url(link)
        cmd = f"yt-dlp -i --get-id --flat-playlist --cookies {self._get_current_cookie_file()} --playlist-end {limit} --skip-download {link}"
        try:
            result = await self._shell_cmd(cmd)
            video_ids = [id for id in result.split("\n") if id]
            return video_ids
        except Exception as e:
            logger.error(f"Error fetching playlist: {str(e)}")
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None) -> Tuple[Dict, str]:
        if videoid:
            link = self.base + link
        metadata = await self._fetch_video_metadata(link)
        track_details = {
            "title": metadata.get("title", ""),
            "link": metadata.get("link", ""),
            "vidid": metadata.get("vidid", ""),
            "duration_min": metadata.get("duration_min", ""),
            "thumb": metadata.get("thumbnail", "")
        }
        return track_details, metadata.get("vidid", "")

    async def formats(self, link: str, videoid: Union[bool, str] = None) -> Tuple[List[Dict], str]:
        if videoid:
            link = self.base + link
        link = self._clean_url(link)
        cache_key = f"formats_{link}"
        if cache_key in metadata_cache:
            return metadata_cache[cache_key], link
        for _ in range(len(self._cookie_files)):
            ydl = yt_dlp.YoutubeDL(self._ytdl_opts)
            try:
                info = ydl.extract_info(link, download=False)
                formats_available = [
                    {
                        "format": format["format"],
                        "filesize": format.get("filesize"),
                        "format_id": format["format_id"],
                        "ext": format["ext"],
                        "format_note": format.get("format_note"),
                        "yturl": link
                    }
                    for format in info["formats"]
                    if "dash" not in str(format.get("format", "")).lower() and all(
                        key in format for key in ["format", "format_id", "ext"]
                    )
                ]
                metadata_cache[cache_key] = formats_available
                return formats_available, link
            except yt_dlp.utils.DownloadError as e:
                if "unavailable" in str(e).lower():
                    logger.warning(f"Video unavailable for formats with current cookie: {str(e)}")
                    self._cycle_cookie_file()
                    continue
                logger.error(f"Error fetching formats: {str(e)}")
                return [], link
            except Exception as e:
                logger.error(f"Unexpected error fetching formats: {str(e)}")
                return [], link
        return [], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None) -> Tuple[str, str, str, str]:
        if videoid:
            link = self.base + link
        link = self._clean_url(link)
        try:
            a = VideosSearch(link, limit=10)
            result = (await a.next()).get("result", [])
            if query_type >= len(result):
                return "", "", "", ""
            return (
                result[query_type]["title"],
                result[query_type]["duration"],
                result[query_type]["thumbnails"][0]["url"].split("?")[0],
                result[query_type]["id"]
            )
        except Exception as e:
            logger.error(f"Error fetching slider data: {str(e)}")
            return "", "", "", ""

    async def _download_audio_from_api(self, link: str, retries: int = 3, backoff: float = 1.0) -> Optional[str]:
        if not self._mp3_api_url:
            logger.warning("No MP3 API URL provided in config.")
            return None

        match = self.video_id_pattern.search(link)
        if not match:
            logger.error(f"Invalid YouTube URL: {link}")
            return None
        video_id = match.group(1)
        file_path = os.path.join("downloads", f"{video_id}.m4a")

        if os.path.exists(file_path):
            logger.info(f"File {file_path} already exists. Skipping download.")
            return file_path

        async def try_api(attempt):
            session = await self._ensure_session()
            url = self._mp3_api_url.format(link)
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "success" and data.get("download_url"):
                            async with session.get(data["download_url"], timeout=30) as dl_response:
                                if dl_response.status == 200:
                                    content = await dl_response.read()
                                    if len(content) > 0:
                                        return content
                                    logger.warning(f"Empty content from download_url: {data['download_url']}")
                                    return None
                        logger.warning(f"API response invalid or failed: {data}")
                        return None
                    logger.warning(f"API request failed with status {response.status} for {url}")
                    return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"API download attempt {attempt} failed for {url}: {str(e)}")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from API: {str(e)}")
                return None

        for attempt in range(retries):
            content = await try_api(attempt + 1)
            if content:
                os.makedirs("downloads", exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(content)
                logger.info(f"Successfully downloaded audio from API: {file_path}")
                return file_path
            if attempt < retries - 1:
                await asyncio.sleep(backoff * (2 ** attempt))
                logger.info(f"Retrying API download, attempt {attempt + 2}")

        logger.error(f"All API attempts failed for video ID {video_id}")
        return None

    async def _download_video_from_api(self, link: str, retries: int = 3, backoff: float = 1.0) -> Optional[str]:
        if not self._video_api_url:
            logger.warning("No video API URL provided in config.")
            return None

        match = self.video_id_pattern.search(link)
        if not match:
            logger.error(f"Invalid YouTube URL: {link}")
            return None
        video_id = match.group(1)
        file_path = os.path.join("downloads", f"{video_id}.mp4")

        if os.path.exists(file_path):
            logger.info(f"File {file_path} already exists. Skipping download.")
            return file_path

        async def try_api(attempt):
            session = await self._ensure_session()
            url = self._video_api_url.format(link)
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "success" and data.get("download_url"):
                            async with session.get(data["download_url"], timeout=30) as dl_response:
                                if dl_response.status == 200:
                                    content = await dl_response.read()
                                    if len(content) > 0:
                                        return content
                                    logger.warning(f"Empty content from download_url: {data['download_url']}")
                                    return None
                        logger.warning(f"API response invalid or failed: {data}")
                        return None
                    logger.warning(f"API request failed with status {response.status} for {url}")
                    return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"API download attempt {attempt} failed for {url}: {str(e)}")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from API: {str(e)}")
                return None

        for attempt in range(retries):
            content = await try_api(attempt + 1)
            if content:
                os.makedirs("downloads", exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(content)
                logger.info(f"Successfully downloaded video from API: {file_path}")
                return file_path
            if attempt < retries - 1:
                await asyncio.sleep(backoff * (2 ** attempt))
                logger.info(f"Retrying API download, attempt {attempt + 2}")

        logger.error(f"All API attempts failed for video ID {video_id}")
        return None

    async def _check_file_size(self, link: str) -> Optional[int]:
        link = self._clean_url(link)
        cache_key = f"size_{link}"
        if cache_key in file_size_cache:
            return file_size_cache[cache_key]

        for _ in range(len(self._cookie_files)):
            ydl = yt_dlp.YoutubeDL(self._ytdl_opts)
            try:
                info = ydl.extract_info(link, download=False)
                total_size = sum(format.get("filesize", 0) for format in info.get("formats", []))
                file_size_cache[cache_key] = total_size
                return total_size
            except yt_dlp.utils.DownloadError as e:
                if "unavailable" in str(e).lower():
                    logger.warning(f"Video unavailable for size check: {str(e)}")
                    self._cycle_cookie_file()
                    continue
                logger.error(f"Error checking file size: {str(e)}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error checking file size: {str(e)}")
                return None
        return None

    async def _shell_cmd(self, cmd: str) -> str:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, error = await proc.communicate()
        if error and "unavailable videos are hidden" not in error.decode("utf-8").lower():
            logger.error(f"Shell command error: {error.decode('utf-8')}")
            return error.decode("utf-8")
        return out.decode("utf-8")

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> Tuple[Optional[str], bool]:
        if videoid:
            link = self.base + link
        link = self._clean_url(link)
        loop = asyncio.get_running_loop()

        def audio_dl() -> str:
            ydl_optssx = {
                **self._ytdl_opts,
                "format": "bestaudio[acodec=opus]/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "opus",
                    "preferredquality": "192",
                }],
                "prefer_ffmpeg": True,
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, download=False)
                xyz = os.path.join("downloads", f"{info['id']}.opus")
                if os.path.exists(xyz):
                    return xyz
                x.download([link])
                return xyz

        def video_dl() -> str:
            ydl_optssx = {
                **self._ytdl_opts,
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=opus])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "merge_output_format": "mp4",
                "prefer_ffmpeg": True,
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as x:
                x.download([link])

        for _ in range(len(self._cookie_files)):
            try:
                if songvideo:
                    await loop.run_in_executor(None, song_video_dl)
                    return f"downloads/{title}.mp4", True
                elif songaudio:
                    await loop.run_in_executor(None, song_audio_dl)
                    return f"downloads/{title}.opus", True
                elif video:
                    downloaded_file = await self._download_video_from_api(link)
                    if downloaded_file:
                        return downloaded_file, True
                    if await is_on_off(1):
                        return await loop.run_in_executor(None, video_dl), True
                    else:
                        file_size = await self._check_file_size(link)
                        if file_size and file_size / (1024 * 1024) > 250:
                            logger.warning(f"File size {file_size / (1024 * 1024):.2f} MB exceeds 250MB limit.")
                            return None, False
                        return await loop.run_in_executor(None, video_dl), True
                else:
                    downloaded_file = await self._download_audio_from_api(link)
                    if downloaded_file:
                        return downloaded_file, True
                    return await loop.run_in_executor(None, audio_dl), True
            except yt_dlp.utils.DownloadError as e:
                if "unavailable" in str(e).lower():
                    logger.warning(f"Video unavailable with current cookie: {str(e)}")
                    self._cycle_cookie_file()
                    continue
                logger.error(f"Download failed: {str(e)}")
                return None, False
            except Exception as e:
                logger.error(f"Unexpected download error: {str(e)}")
                return None, False
        logger.error(f"Download failed after trying all cookies for {link}")
        return None, False

async def main():
    async with YouTubeAPI() as yt:
        if not yt._mp3_api_url or not yt._video_api_url:
            logger.error("API_URL1 or API_URL2 not set in config.")
            return
        link = "https://www.youtube.com/watch?v=1onhvVnL8B8"
        try:
            result, direct = await yt.download(link, None, video=False)
            logger.info(f"Downloaded file: {result}, Direct: {direct}")
        except Exception as e:
            logger.error(f"Main execution failed: {str(e)}")
