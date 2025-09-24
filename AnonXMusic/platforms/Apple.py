import re
from typing import Union

import aiohttp
from bs4 import BeautifulSoup
from youtubesearchpython.__future__ import VideosSearch


class AppleAPI:
    def __init__(self):
        self.regex = r"^(https:\/\/music.apple.com\/)(.*)$"
        self.base = "https://music.apple.com/in/playlist/"

    async def valid(self, link: str):
        return bool(re.search(self.regex, link))

    async def track(self, url, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")

        # Extract metadata
        track_name = None
        artist_name = None
        for tag in soup.find_all("meta"):
            if tag.get("property") == "og:title":
                track_name = tag.get("content")
            elif tag.get("name") == "twitter:audio:artist_name":
                artist_name = tag.get("content")

        # 🔹 Fallback: from URL
        if not track_name:
            try:
                slug = url.split("/song/")[1].split("/")[0]
                track_name = slug.replace("-", " ")
            except Exception:
                return False

        search_query = f"{track_name} {artist_name}" if artist_name else track_name

        results = VideosSearch(search_query, limit=1)
        yt_result = (await results.next())["result"]
        if not yt_result:
            return False

        data = yt_result[0]
        track_details = {
            "title": data["title"],
            "link": data["link"],
            "vidid": data["id"],
            "duration_min": data.get("duration"),
            "thumb": data["thumbnails"][0]["url"].split("?")[0],
        }
        return track_details, data["id"]

    async def playlist(self, url, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url
        playlist_id = url.split("playlist/")[1]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        applelinks = soup.find_all("meta", attrs={"property": "music:song"})
        results = []

        for item in applelinks:
            try:
                track_url = item["content"]

                # Try to get track name from slug
                slug = track_url.split("/album/")[1].split("/")[0]
                track_name = slug.replace("-", " ")

                # Search on YouTube
                search_query = track_name
                yt_results = VideosSearch(search_query, limit=1)
                yt_data = (await yt_results.next())["result"]

                if yt_data:
                    yt_info = yt_data[0]
                    track_details = {
                        "title": yt_info["title"],
                        "link": yt_info["link"],
                        "vidid": yt_info["id"],
                        "duration_min": yt_info.get("duration"),
                        "thumb": yt_info["thumbnails"][0]["url"].split("?")[0],
                    }
                    results.append(track_details)
                else:
                    results.append({"title": track_name, "link": None})

            except Exception:
                continue

        return results, playlist_id
