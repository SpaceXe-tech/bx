# Use slim Debian-based Python image
FROM python:3.10-slim-bullseye

# Install system dependencies: curl, gnupg, ffmpeg, git, nodejs
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg ffmpeg git \
    && curl -fsSL https://deb.nodesource.com/setup_19.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy bot source code into image
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Default command to run the bot
CMD ["python3", "-m", "AnonXMusic"]
