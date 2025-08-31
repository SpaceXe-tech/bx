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
from config import API_URL2, API_KEY
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from AnonXMusic.utils.database import is_on_off
from AnonXMusic.utils.formatters import time_to_seconds
from .. import LOGGER

logger = LOGGER(__name__)

# Simple timeout settings
TIMEOUT = 30
DOWNLOAD_TIMEOUT = 30
MAX_SIZE_MB = 500

def cookie_txt_file():
    folder_path = os.path.join(os.getcwd(), "cookies")
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in cookies folder.")
    return random.choice(txt_files)

async def download_with_api2(video_id: str, download_mode: str = "audio") -> Optional[str]:
    """Simple API2 download"""
    if not API_URL2:
        return None
    
    try:
        file_ext = "mp3" if download_mode == "audio" else "mp4"
        file_path = os.path.join("downloads", f"{video_id}.{file_ext}")
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
        
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        format_param = "mp3" if download_mode == "audio" else "mp4"
        api_url = f"{API_URL2}?url={youtube_url}&format={format_param}"
        
        response = requests.get(api_url, timeout=TIMEOUT)
        if response.status_code != 200:
            return None
        
        data = response.json()
        download_url = data.get("data", {}).get("download", {}).get("url")
        if not download_url:
            return None
        
        with requests.get(download_url, stream=True, timeout=DOWNLOAD_TIMEOUT) as dl_response:
            if dl_response.status_code != 200:
                return None
            
            os.makedirs("downloads", exist_ok=True)
            with open(file_path, "wb") as f:
                for chunk in dl_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if os.path.getsize(file_path) > 0:
                logger.info(f"API2 success: {video_id}")
                return file_path
        
        return None
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        return None

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.listbase = "https://youtube.com/playlist?list="

    def extract_video_id(self, link: str) -> str:
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([0-9A-Za-z_-]{11})',
            r'youtube\.com\/v\/([0-9A-Za-z_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        
        if re.match(r'^[0-9A-Za-z_-]{11}$', link):
            return link
            
        raise ValueError(f"Invalid YouTube link: {link}")

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

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
                            return text[entity.offset: entity.offset + entity.length]
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
        except:
            return {}

    async def info(self, link: str, videoid: Union[bool, str] = None) -> Tuple[str, str, int, str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
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
            except:
                pass
        
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        result = await self._get_info(link)
        return result.get("title", "")

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        result = await self._get_info(link)
        return result.get("duration", "")

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        result = await self._get_info(link)
        thumbnails = result.get("thumbnails", [])
        return thumbnails[0].get("url", "").split("?")[0] if thumbnails else ""

    async def video(self, link: str, videoid: Union[bool, str] = None) -> Tuple[int, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "yt-dlp", "--cookies", cookie_txt_file(), "-g", 
                    "-f", "best[height<=?720][width<=?1280]", link,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=TIMEOUT
            )
            
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
            
            if stdout:
                url = stdout.decode().split("\n")[0].strip()
                return (1, url) if url else (0, "No URL found")
            else:
                return 0, stderr.decode()
        except:
            return 0, "Timeout or error occurred"

    async def playlist(self, link: str, limit: int, user_id: int, videoid: Union[bool, str] = None) -> list:
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            cmd = f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                ),
                timeout=TIMEOUT
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
            result = [item.strip() for item in stdout.decode().split("\n") if item.strip()]
            return result
        except:
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None) -> Tuple[Dict[str, Any], str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        result = await self._get_info(link)
        if not result:
            return {}, ""
        
        track_details = {
            "title": result.get("title", ""),
            "link": result.get("link", ""),
            "vidid": result.get("id", ""),
            "duration_min": result.get("duration", ""),
            "thumb": result.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
        }
        return track_details, result.get("id", "")

    async def formats(self, link: str, videoid: Union[bool, str] = None) -> Tuple[list, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            def get_formats():
                ydl = yt_dlp.YoutubeDL({"quiet": True, "cookiefile": cookie_txt_file()})
                formats_available = []
                with ydl:
                    r = ydl.extract_info(link, download=False)
                    for format in r.get("formats", []):
                        if all(key in format for key in ["format", "format_id", "ext"]):
                            if "dash" not in str(format["format"]).lower():
                                formats_available.append({
                                    "format": format["format"],
                                    "filesize": format.get("filesize"),
                                    "format_id": format["format_id"],
                                    "ext": format["ext"],
                                    "format_note": format.get("format_note", ""),
                                    "yturl": link,
                                })
                return formats_available
            
            formats = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, get_formats),
                timeout=TIMEOUT
            )
            return formats, link
        except:
            return [], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None) -> Tuple[str, str, str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
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
                    item.get("id", "")
                )
        except:
            pass
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
        
        os.makedirs("downloads", exist_ok=True)
        
        def ytdlp_audio():
            try:
                opts = {
                    "format": "bestaudio/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "no_warnings": True,
                }
                
                ydl = yt_dlp.YoutubeDL(opts)
                info = ydl.extract_info(link, download=False)
                if not info:
                    return None
                
                file_path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return file_path
                
                ydl.download([link])
                return file_path if os.path.exists(file_path) and os.path.getsize(file_path) > 0 else None
            except:
                return None

        def ytdlp_video():
            try:
                opts = {
                    "format": "best[height<=720][ext=mp4]/best[ext=mp4]/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "no_warnings": True,
                }
                
                ydl = yt_dlp.YoutubeDL(opts)
                info = ydl.extract_info(link, download=False)
                if not info:
                    return None
                
                file_path = os.path.join("downloads", f"{info['id']}.mp4")
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return file_path
                
                ydl.download([link])
                return file_path if os.path.exists(file_path) and os.path.getsize(file_path) > 0 else None
            except:
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
                }
                
                ydl = yt_dlp.YoutubeDL(opts)
                ydl.download([link])
                
                result_path = f"downloads/{title}.mp4"
                return result_path if os.path.exists(result_path) and os.path.getsize(result_path) > 0 else None
            except:
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
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                }
                
                ydl = yt_dlp.YoutubeDL(opts)
                ydl.download([link])
                
                result_path = f"downloads/{title}.mp3"
                return result_path if os.path.exists(result_path) and os.path.getsize(result_path) > 0 else None
            except:
                return None

        try:
            loop = asyncio.get_running_loop()
            
            if songvideo:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, ytdlp_song_video),
                    timeout=DOWNLOAD_TIMEOUT
                )
                return result, result is not None
                
            elif songaudio:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, ytdlp_song_audio),
                    timeout=DOWNLOAD_TIMEOUT
                )
                return result, result is not None
                
            elif video:
                # Try API2 first for video
                api_result = await download_with_api2(video_id, "video")
                if api_result:
                    return api_result, True
                
                # Fallback to yt-dlp
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, ytdlp_video),
                    timeout=DOWNLOAD_TIMEOUT
                )
                return result, result is not None
            
            else:  # Audio download
                # Check existing files
                for ext in ['.m4a', '.mp3', '.webm']:
                    existing_file = os.path.join("downloads", f"{video_id}{ext}")
                    if os.path.exists(existing_file) and os.path.getsize(existing_file) > 0:
                        return existing_file, True
                
                # Try API2 first
                api_result = await download_with_api2(video_id, "audio")
                if api_result:
                    return api_result, True
                
                # Fallback to yt-dlp
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, ytdlp_audio),
                    timeout=DOWNLOAD_TIMEOUT
                )
                return result, result is not None
                
        except asyncio.TimeoutError:
            logger.error(f"Download timeout: {video_id}")
            return None, False
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return None, False
