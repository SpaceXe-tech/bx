import os
import re
import json
import glob
import random
import yt_dlp
import time
import aiohttp
import asyncio
import aiofiles
import requests
from typing import Union, Tuple, Optional
from config import API_URL1, API_URL2, API_KEY
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from AnonXMusic.utils.database import is_on_off
from AnonXMusic.utils.formatters import time_to_seconds
from .. import LOGGER

logger = LOGGER(__name__)


def cookie_txt_file():
    folder_path = os.path.join(os.getcwd(), "cookies")
    log_path = os.path.join(folder_path, "logs.csv")
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the specified folder.")
    cookie_txt_file = random.choice(txt_files)
    with open(log_path, 'a') as file:
        file.write(f'Chosen File : {cookie_txt_file}\n')
    return cookie_txt_file


async def check_file_size(link):
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J", link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    formats = info.get('formats', [])
    if not formats:
        logger.error("No formats found.")
        return None
    return parse_size(formats)


async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    return out.decode("utf-8") if out else errorz.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.video_id_pattern = re.compile(r"(?:v=|youtu\.be/|youtube\.com/(?:embed/|v/|watch\?v=))([0-9A-Za-z_-]{11})")
        self._api_url = API_URL1
        self._api_key = API_KEY
        self._session = None

    def extract_video_id(self, link: str) -> str:
        patterns = [
            r'youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)([0-9A-Za-z_-]{11})',
            r'youtu\.be\/([0-9A-Za-z_-]{11})',
            r'youtube\.com\/(?:playlist\?list=[^&]+&v=|v\/)([0-9A-Za-z_-]{11})',
            r'youtube\.com\/(?:.*\?v=|.*\/)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        raise ValueError("Invalid YouTube link provided.")

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(limit=100)
            )
        return self._session

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _download_from_api(self, link: str, download_mode: str, retries: int = 3, backoff: float = 1.0) -> Optional[str]:
        if not self._api_url:
            logger.warning("No API URL provided in config.")
            return None

        if "&" in link:
            link = link.split("&")[0]

        match = self.video_id_pattern.search(link)
        if not match:
            logger.error(f"Invalid YouTube URL: {link}")
            return None

        video_id = match.group(1)
        file_ext = "mp3" if download_mode == "audio" else "mp4"
        file_path = os.path.join("downloads", f"{video_id}.{file_ext}")

        if os.path.exists(file_path):
            logger.info(f"File {file_path} already exists. Skipping download.")
            return file_path

        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        api_url = f"{self._api_url}?url={youtube_url}&apiKey={self._api_key}"
        logger.info(f"Trying API_URL: {api_url}")

        async def try_api(attempt):
            session = await self._ensure_session()
            try:
                async with session.get(api_url, timeout=30) as response:
                    if response.status != 200:
                        logger.warning(f"API request failed with status {response.status} for {api_url}")
                        return None

                    try:
                        data = await response.json()
                    except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                        logger.error(f"Failed to parse API JSON response: {str(e)}")
                        return None

                    if (
                        data.get("status") == 200 and
                        data.get("successful") == "success" and
                        data.get("data", {}).get("url")
                    ):
                        download_url = data["data"]["url"]
                        filename = data["data"].get("filename", f"{video_id}.{file_ext}")

                        async with session.get(download_url, timeout=60) as dl_response:
                            if dl_response.status != 200:
                                logger.warning(f"Download request failed with status {dl_response.status} for {download_url}")
                                return None

                            os.makedirs("downloads", exist_ok=True)
                            try:
                                async with aiofiles.open(file_path, 'wb') as f:
                                    async for chunk in dl_response.content.iter_chunked(8192):
                                        await f.write(chunk)
                            except Exception as e:
                                logger.warning(f"Exception during download write: {e}")
                                return None

                            if os.path.getsize(file_path) > 0:
                                logger.info(f"Successfully downloaded {download_mode} from API: {file_path}")
                                same_file = os.path.join("downloads", filename)
                                if file_path != same_file and os.path.exists(same_file):
                                    os.remove(same_file)
                                if file_path != same_file:
                                    os.rename(file_path, same_file)
                                return same_file
                            else:
                                logger.warning(f"Empty file downloaded from {download_url}")
                                os.remove(file_path)
                                return None

                    logger.warning(f"API response invalid or incomplete: {data}")
                    return None

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"API download attempt {attempt} failed for {api_url}: {str(e)}")
                return None

        for attempt in range(retries):
            result = await try_api(attempt + 1)
            if result:
                return result
            if attempt < retries - 1:
                await asyncio.sleep(backoff * (2 ** attempt))
                logger.info(f"Retrying API download, attempt {attempt + 2}")

        logger.error(f"All API attempts failed for URL {link} with mode {download_mode}")
        return None

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset is None:
            return None
        return text[offset: offset + length]

        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid
    
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
        if "&" in link:
            link = link.split("&")[0]
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, download=False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, download=False)
            xyz = os.path.join("downloads", f"{info['id']}.mp4")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            return f"downloads/{title}.mp4"

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "opus",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            return f"downloads/{title}.mp3"

        try:
            if songvideo:
                return await loop.run_in_executor(None, song_video_dl), True
            elif songaudio:
                return await loop.run_in_executor(None, song_audio_dl), True
            elif video:
                downloaded_file = await self._download_from_api(link, download_mode="video")
                if downloaded_file:
                    return downloaded_file, True
                logger.info("Falling back to cookie-based video download")
                if await is_on_off(1):
                    return await loop.run_in_executor(None, video_dl), True
                else:
                    file_size = await check_file_size(link)
                    if not file_size:
                        logger.error("Could not determine file size.")
                        return None, False
                    total_size_mb = file_size / (1024 * 1024)
                    if total_size_mb > 250:
                        logger.warning(f"File size {total_size_mb:.2f} MB exceeds the 250MB limit.")
                        return None, False
                    return await loop.run_in_executor(None, video_dl), True
            else:
                # Try API_URL2 first
                video_id = self.extract_video_id(link)
                file_path = os.path.join("downloads", f"{video_id}.mp3")
                if os.path.exists(file_path):
                    logger.info(f"{file_path} already exists. Skipping download.")
                    return file_path, True

                os.makedirs("downloads", exist_ok=True)
                try:
                    logger.info(f"Trying download with API_URL2 for video ID: {video_id}")
                    response = requests.get(f"{API_URL2}?url=https://www.youtube.com/watch?v={video_id}", timeout=30)
                    data = response.json()

                    if data.get("success"):
                        for url in [data.get("directLink"), data.get("downloads")]:
                            if not url:
                                continue
                            try:
                                logger.info(f"Attempting download from API_URL2: {url}")
                                with requests.get(url, stream=True, timeout=30) as download_response:
                                    if download_response.status_code == 200:
                                        with open(file_path, "wb") as f:
                                            for chunk in download_response.iter_content(chunk_size=8192):
                                                if chunk:
                                                    f.write(chunk)
                                        logger.info(f"Successfully downloaded {file_path} from API_URL2")
                                        return file_path, True
                                    else:
                                        logger.warning(f"Download failed with status {download_response.status_code}")
                            except requests.RequestException as e:
                                logger.error(f"Download error from {url}: {e}")
                    else:
                        logger.warning("API_URL2 returned failure status.")
                except Exception as e:
                    logger.error(f"Error with API_URL2: {e}")

                # Fallback to API_URL1
                logger.info("Falling back to API_URL1")
                downloaded_file = await self._download_from_api(link, download_mode="audio")
                if downloaded_file:
                    logger.info(f"Successfully downloaded {downloaded_file} from API_URL1")
                    return downloaded_file, True

                # Fallback to cookie-based audio download
                logger.info("Falling back to cookie-based audio download")
                return await loop.run_in_executor(None, audio_dl), True
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            return None, False
