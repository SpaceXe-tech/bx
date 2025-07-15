import os
import aiohttp
import aiofiles

from AnonXMusic import app
import config
from ..logging import LOGGER


async def fetch_content(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.read()
    except aiohttp.ClientError as e:
        LOGGER(__name__).error(f"Error fetching from {url}: {e}")
        return b""


async def save_file(content: bytes, file_path: str):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        async with aiofiles.open(file_path, "wb") as file:
            await file.write(content)
        return file_path
    except Exception as e:
        LOGGER(__name__).error(f"Error saving file {file_path}: {e}")
        return ""


def is_malformed_or_cloned(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines or not lines[0].strip().startswith("# Netscape HTTP Cookie File"):
            return True

        stripped = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
        return len(stripped) != len(set(stripped))

    except Exception as e:
        LOGGER(__name__).warning(f"Error validating cookies file: {e}")
        return True


async def download_and_validate(url: str, file_path: str) -> bool:
    async with aiohttp.ClientSession() as session:
        content = await fetch_content(session, url)

        if not content:
            LOGGER(__name__).error("No content fetched from cookies URL Or Url Isnt Assigned In Config py.")
            return False

        saved_path = await save_file(content, file_path)
        if saved_path and os.path.getsize(saved_path) > 0:
            if is_malformed_or_cloned(saved_path):
                os.remove(saved_path)
                LOGGER(__name__).error("Downloaded cookies.txt is malformed or cloned. Deleted.")
                return False
            LOGGER(__name__).info(f"Cookies saved successfully to {saved_path}.")
            return True

        LOGGER(__name__).error("Failed to save cookies or the file is empty.")
        return False


async def save_cookies():
    file_path = "cookies/cookies.txt"
    url = str(config.COOKIES)

    if os.path.exists(file_path):
        if os.path.getsize(file_path) == 0 or is_malformed_or_cloned(file_path):
            LOGGER(__name__).warning("Existing cookies.txt is empty or malformed. Deleting.")
            os.remove(file_path)
        else:
            LOGGER(__name__).info("Valid cookies.txt already exists. Skipping download.")
            return

    success = await download_and_validate(url, file_path)

    if not success:
        LOGGER(__name__).warning("Retrying cookies download after cleanup...")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to delete cookies.txt before retry: {e}")
        await asyncio.sleep(1)
        await download_and_validate(url, file_path)
