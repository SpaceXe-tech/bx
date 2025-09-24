import re
import json
from typing import Union
from urllib.parse import urlparse, unquote

import aiohttp
from bs4 import BeautifulSoup
from youtubesearchpython.__future__ import VideosSearch


class AppleAPI:
    def __init__(self):
        self.regex = r"^(https:\/\/music.apple.com\/)(.*)$"
        self.base = "https://music.apple.com/in/playlist/"
        # Use a browser-like UA; Apple sometimes serves different markup to unknown clients
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    async def valid(self, link: str):
        return bool(re.search(self.regex, link))

    async def _fetch(self, url: str):
        """Fetch page HTML with friendly headers. Returns text or False on failure."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, allow_redirects=True, timeout=15) as resp:
                    if resp.status != 200:
                        return False
                    return await resp.text()
        except Exception:
            return False

    async def _yt_search(self, query: str):
        """Return list of YouTube search results (may be empty)."""
        try:
            vs = VideosSearch(query, limit=1)
            out = await vs.next()
            return out.get("result", []) if isinstance(out, dict) else []
        except Exception:
            return []

    async def track(self, url, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url

        html = await self._fetch(url)
        if not html:
            return False

        soup = BeautifulSoup(html, "html.parser")

        # 1) Try JSON-LD (best shot)
        track_name = None
        artist_name = None
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                payload = json.loads(script.string or script.text)
            except Exception:
                continue

            # payload can be dict or list
            candidates = payload if isinstance(payload, list) else [payload]
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                t = item.get("@type", "").lower()
                if "music" in t or "musicrecording" in t or "musicvideo" in t or "musicplaylist" in t:
                    # name
                    if not track_name:
                        track_name = item.get("name") or item.get("headline") or track_name
                    # artist - can be dict or list or string
                    by = item.get("byArtist") or item.get("author") or item.get("artist")
                    if by:
                        if isinstance(by, dict):
                            artist_name = by.get("name") or artist_name
                        elif isinstance(by, list) and by:
                            if isinstance(by[0], dict):
                                artist_name = by[0].get("name") or artist_name
                            elif isinstance(by[0], str):
                                artist_name = by[0]
                        elif isinstance(by, str):
                            artist_name = by
                if track_name:
                    break
            if track_name:
                break

        # 2) Meta tag fallbacks
        if not track_name:
            og = soup.find("meta", {"property": "og:title"})
            if og and og.get("content"):
                track_name = og.get("content").strip()

        if not artist_name:
            ta = soup.find("meta", {"name": "twitter:audio:artist_name"})
            if ta and ta.get("content"):
                artist_name = ta.get("content").strip()

        # Try parsing description for artist hints: "Song • Artist" or "Song — Artist"
        if not artist_name:
            meta_desc = (soup.find("meta", {"property": "og:description"}) or soup.find("meta", {"name": "description"}))
            if meta_desc and meta_desc.get("content"):
                desc = meta_desc.get("content")
                # try common separators
                for sep in ["•", "—", "-", "–", "|"]:
                    if sep in desc:
                        parts = [p.strip() for p in desc.split(sep) if p.strip()]
                        if len(parts) > 1:
                            # heuristics: artist often second
                            artist_name = parts[1]
                            break
                # fallback: "by <artist>"
                if not artist_name:
                    m = re.search(r"by\s+([^\-•|–—]+)", desc, re.IGNORECASE)
                    if m:
                        artist_name = m.group(1).strip()

        # 3) Final fallback: extract slug from the URL
        if not track_name:
            try:
                parsed = urlparse(url)
                parts = [p for p in parsed.path.split("/") if p]
                slug = None
                if "song" in parts:
                    idx = parts.index("song")
                    if len(parts) > idx + 1:
                        slug = parts[idx + 1]
                elif "album" in parts:
                    idx = parts.index("album")
                    if len(parts) > idx + 1:
                        slug = parts[idx + 1]
                else:
                    # pick nearest hyphenated segment (common 'track-name' slugs)
                    for p in reversed(parts):
                        if "-" in p:
                            slug = p
                            break
                if slug:
                    track_name = unquote(slug).replace("-", " ")
            except Exception:
                return False

        if not track_name:
            return False

        # Build search query & try YouTube
        search_query = f"{track_name} {artist_name}" if artist_name else track_name
        yt_results = await self._yt_search(search_query)

        # Fallback to track_name only
        if not yt_results:
            yt_results = await self._yt_search(track_name)

        if not yt_results:
            return False

        d = yt_results[0]
        track_details = {
            "title": d.get("title"),
            "link": d.get("link"),
            "vidid": d.get("id"),
            "duration_min": d.get("duration"),
            "thumb": (d.get("thumbnails") or [{"url": None}])[0].get("url", "").split("?")[0],
        }
        return track_details, d.get("id")

    async def playlist(self, url, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url

        # safe extraction of playlist id (strip queries)
        try:
            playlist_id = url.split("playlist/")[1].split("?")[0]
        except Exception:
            playlist_id = url

        html = await self._fetch(url)
        if not html:
            return False

        soup = BeautifulSoup(html, "html.parser")
        applelinks = soup.find_all("meta", attrs={"property": "music:song"})
        results = []

        for item in applelinks:
            try:
                track_url = item.get("content")
                if not track_url:
                    continue

                # Prefer to reuse track() (it will fetch the track page for better metadata)
                mapped = await self.track(track_url)
                if mapped:
                    # track() returns (track_details, vidid)
                    track_details, _ = mapped
                    results.append(track_details)
                    continue

                # If track() failed, fallback: extract slug from the content url and YouTube-search it
                parsed = urlparse(track_url)
                parts = [p for p in parsed.path.split("/") if p]
                slug = None
                if "song" in parts:
                    idx = parts.index("song")
                    if len(parts) > idx + 1:
                        slug = parts[idx + 1]
                elif "album" in parts:
                    idx = parts.index("album")
                    if len(parts) > idx + 1:
                        slug = parts[idx + 1]
                else:
                    for p in reversed(parts):
                        if "-" in p:
                            slug = p
                            break

                if not slug:
                    # final fallback: store raw content url as title
                    results.append({"title": track_url, "link": None})
                    continue

                fallback_title = unquote(slug).replace("-", " ")
                yt = await self._yt_search(fallback_title)
                if yt:
                    td = yt[0]
                    results.append(
                        {
                            "title": td.get("title"),
                            "link": td.get("link"),
                            "vidid": td.get("id"),
                            "duration_min": td.get("duration"),
                            "thumb": (td.get("thumbnails") or [{"url": None}])[0].get("url", "").split("?")[0],
                        }
                    )
                else:
                    results.append({"title": fallback_title, "link": None})
            except Exception:
                # keep going if an item fails
                continue

        return results, playlist_id
