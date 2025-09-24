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

        if not track_name:
            return False

        # Build refined query
        search_query = f"{track_name} {artist_name}" if artist_name else track_name

        # Search YouTube
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
                # Extract track slug cleanly
                slug = (item["content"].split("album/")[1]).split("/")[0]
                xx = slug.replace("-", " ")
            except Exception:
                xx = (item["content"].split("album/")[1]).split("/")[0]
            results.append(xx)

        return results, playlist_id
