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
from typing import Union, Tuple, Optional, Dict, Any
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


async def check_file_size(link: str) -> Optional[int]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J", link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return None
        
        info = json.loads(stdout.decode())
        formats = info.get('formats', [])
        if not formats:
            return None
        
        total_size = sum(fmt.get('filesize', 0) for fmt in formats if fmt.get('filesize'))
        return total_size
    except Exception:
        return None


async def shell_cmd(cmd: str) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, errorz = await proc.communicate()
        return out.decode("utf-8") if out else errorz.decode("utf-8")
    except Exception as e:
        return str(e)


# Standalone API Functions
async def download_with_api1(video_id: str, download_mode: str = "audio") -> Optional[str]:
    """Standalone API 1 download function"""
    if not API_URL1 or not API_KEY:
        return None
    
    try:
        file_ext = "mp3" if download_mode == "audio" else "mp4"
        file_path = os.path.join("downloads", f"{video_id}.{file_ext}")
        
        if os.path.exists(file_path):
            return file_path
        
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        api_url = f"{API_URL1}?url={youtube_url}&apiKey={API_KEY}"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if not (data.get("status") == 200 and 
                       data.get("successful") == "success" and 
                       data.get("data", {}).get("url")):
                    return None
                
                download_url = data["data"]["url"]
                filename = data["data"].get("filename", f"{video_id}.{file_ext}")
                
                async with session.get(download_url, timeout=60) as dl_response:
                    if dl_response.status != 200:
                        return None
                    
                    os.makedirs("downloads", exist_ok=True)
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in dl_response.content.iter_chunked(8192):
                            await f.write(chunk)
                    
                    if os.path.getsize(file_path) > 0:
                        final_path = os.path.join("downloads", filename)
                        if file_path != final_path:
                            if os.path.exists(final_path):
                                os.remove(final_path)
                            os.rename(file_path, final_path)
                        logger.info(f"API 1 success: {video_id}")
                        return final_path
                    
        return None
    except Exception:
        logger.info(f"API 1 failed: {video_id}")
        return None


async def download_with_api2(video_id: str, download_mode: str = "audio") -> Optional[str]:
    """Standalone API 2 download function"""
    if not API_URL2:
        return None
    
    try:
        file_ext = "mp3" if download_mode == "audio" else "mp4"
        file_path = os.path.join("downloads", f"{video_id}.{file_ext}")
        
        if os.path.exists(file_path):
            return file_path
        
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        format_param = "mp3" if download_mode == "audio" else "mp4"
        api_url = f"{API_URL2}?url={youtube_url}&format={format_param}"
        
        response = requests.get(api_url, timeout=30)
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not (data.get("status") == 200 and 
               data.get("successful") == "success" and 
               data.get("data", {}).get("download", {}).get("url")):
            return None
        
        download_url = data["data"]["download"]["url"]
        
        with requests.get(download_url, stream=True, timeout=30) as download_response:
            if download_response.status_code != 200:
                return None
            
            os.makedirs("downloads", exist_ok=True)
            with open(file_path, "wb") as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if os.path.getsize(file_path) > 0:
                logger.info(f"API 2 success: {video_id}")
                return file_path
        
        return None
    except Exception:
        logger.info(f"API 2 failed: {video_id}")
        return None


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.video_id_pattern = re.compile(r"(?:v=|youtu\.be/|youtube\.com/(?:embed/|v/|watch\?v=))([0-9A-Za-z_-]{11})")

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

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Optional[str]:
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

    async def info(self, link: str, videoid: Union[bool, str] = None) -> Tuple[str, str, int, str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min != "None" else 0
            return title, duration_min, duration_sec, thumbnail, vidid
        except Exception:
            return "", "", 0, "", ""

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            return result["title"]
        except Exception:
            return ""

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            return result["duration"]
        except Exception:
            return ""

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            return result["thumbnails"][0]["url"].split("?")[0]
        except Exception:
            return ""

    async def video(self, link: str, videoid: Union[bool, str] = None) -> Tuple[int, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
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
        except Exception as e:
            return 0, str(e)

    async def playlist(self, link: str, limit: int, user_id: int, videoid: Union[bool, str] = None) -> list:
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            playlist = await shell_cmd(
                f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
            )
            result = [item for item in playlist.split("\n") if item.strip()]
            return result
        except Exception:
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None) -> Tuple[Dict[str, Any], str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            track_details = {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result["duration"],
                "thumb": result["thumbnails"][0]["url"].split("?")[0],
            }
            return track_details, result["id"]
        except Exception:
            return {}, ""

    async def formats(self, link: str, videoid: Union[bool, str] = None) -> Tuple[list, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
            ydl = yt_dlp.YoutubeDL(ytdl_opts)
            formats_available = []
            
            with ydl:
                r = ydl.extract_info(link, download=False)
                for format in r.get("formats", []):
                    if not all(key in format for key in ["format", "filesize", "format_id", "ext", "format_note"]):
                        continue
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append({
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        })
            return formats_available, link
        except Exception:
            return [], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None) -> Tuple[str, str, str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            a = VideosSearch(link, limit=10)
            result = (await a.next()).get("result", [])
            if query_type < len(result):
                item = result[query_type]
                return (
                    item["title"],
                    item["duration"],
                    item["thumbnails"][0]["url"].split("?")[0],
                    item["id"]
                )
            return "", "", "", ""
        except Exception:
            return "", "", "", ""

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
        
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            video_id = self.extract_video_id(link)
        except ValueError:
            return None, False
        
        loop = asyncio.get_running_loop()

        def audio_dl():
            try:
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
            except Exception:
                return None

        def video_dl():
            try:
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
            except Exception:
                return None

        def song_video_dl():
            try:
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
            except Exception:
                return None

        def song_audio_dl():
            try:
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
            except Exception:
                return None

        try:
            if songvideo:
                result = await loop.run_in_executor(None, song_video_dl)
                return result, result is not None
            elif songaudio:
                result = await loop.run_in_executor(None, song_audio_dl)
                return result, result is not None
            elif video:
                # Try APIs first for video
                downloaded_file = await download_with_api1(video_id, "video")
                if downloaded_file:
                    return downloaded_file, True
                
                downloaded_file = await download_with_api2(video_id, "video")
                if downloaded_file:
                    return downloaded_file, True
                
                # Check if cookie-based download is allowed
                if await is_on_off(1):
                    result = await loop.run_in_executor(None, video_dl)
                    return result, result is not None
                else:
                    file_size = await check_file_size(link)
                    if not file_size:
                        return None, False
                    
                    total_size_mb = file_size / (1024 * 1024)
                    if total_size_mb > 250:
                        return None, False
                    
                    result = await loop.run_in_executor(None, video_dl)
                    return result, result is not None
            else:  # Audio download
                # Check if file already exists
                file_path = os.path.join("downloads", f"{video_id}.mp3")
                if os.path.exists(file_path):
                    return file_path, True
                
                # Try API 2 first (audio)
                downloaded_file = await download_with_api2(video_id, "audio")
                if downloaded_file:
                    return downloaded_file, True
                
                # Try API 1 (audio)
                downloaded_file = await download_with_api1(video_id, "audio")
                if downloaded_file:
                    return downloaded_file, True
                
                # Fallback to cookie-based download
                result = await loop.run_in_executor(None, audio_dl)
                return result, result is not None
                
        except Exception:
            return None, False
