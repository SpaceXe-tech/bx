import re
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

# Get this value from my.telegram.org/apps
API_ID = "24620300"
API_HASH = "9a098f01aa56c836f2e34aee4b7ef963"

# Get your token from @BotFather on Telegram.
BOT_TOKEN = getenv("BOT_TOKEN")

# Get your mongo url from cloud.mongodb.com
MONGO_DB_URI = getenv("MONGO_DB_URI")

DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 240))

# Chat id of a group for logging bot's activities
LOGGER_ID = int(getenv("LOGGER_ID", None))

# Get this value on Telegram by /id
OWNER_ID = int(getenv("OWNER_ID", 5960968099))

## Fill these variables if you're deploying on heroku.
# Your heroku app name
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
# Get it from http://dashboard.heroku.com/account
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

UPSTREAM_REPO = getenv(
    "UPSTREAM_REPO",
    "https://github.com/BillaSpace/RX7",
)
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "main")
GIT_TOKEN = getenv(
    "GIT_TOKEN", None
)  # Fill this variable if your upstream repository is private

SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/BillaSpace")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/BillaCore")

# Set this to True if you want the assistant to automatically leave chats after an interval
AUTO_LEAVING_ASSISTANT = bool(getenv("AUTO_LEAVING_ASSISTANT", False))

# Get this credentials from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "95f4f5c6df5744698035a0948e801ad9")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "4b03167b38c943c3857333b3f5ea95ea")

# Maximum limit for fetching playlist's track from youtube, spotify, apple links.
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", 500))

# Telegram audio and video file size limit (in bytes)
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 1073741824))
# Checkout https://www.gbmb.org/mb-to-bytes for converting mb to bytes

# Get your pyrogram v2 session from @StringFatherBot on Telegram
STRING1 = getenv("STRING_SESSION", None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)

BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}

START_IMG_URL = getenv(
    "START_IMG_URL", "https://graph.org/file/6b54d8b294fe0b4934713-bb809aee23c5f19aa9.jpg"
)
PING_IMG_URL = getenv(
    "PING_IMG_URL", "https://graph.org/file/6b54d8b294fe0b4934713-bb809aee23c5f19aa9.jpg"
)
PLAYLIST_IMG_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"
STATS_IMG_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"
TELEGRAM_AUDIO_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"
TELEGRAM_VIDEO_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"
STREAM_IMG_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"
SOUNCLOUD_IMG_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"
YOUTUBE_IMG_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"
SPOTIFY_ARTIST_IMG_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"
SPOTIFY_ALBUM_IMG_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"
SPOTIFY_PLAYLIST_IMG_URL = "https://graph.org/file/4491c4c570d9ccb1a19d0-1fb0835d3592780331.jpg"

# Add API_URL1 and API_URL2 loaded from .env
API_URL1 = getenv("API_URL1", None)

def time_to_seconds(string):
    parts = string.split(":")
    return sum(int(x) * 60**i for i, x in enumerate(reversed(parts)))

DURATION_LIMIT = time_to_seconds(f"{DURATION_LIMIT_MIN}:00")

if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHANNEL url is wrong. Please ensure that it starts with https://"
        )

if SUPPORT_CHAT:
    if not re.match("(?:http|https)://", SUPPORT_CHAT):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHAT url is wrong. Please ensure that it starts with https://"
)
