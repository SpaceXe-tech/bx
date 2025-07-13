FROM python:3.10-slim-bullseye

# Install required tools and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 19
RUN curl -fsSL https://deb.nodesource.com/setup_19.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app/

# Install Python requirements
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Default command
CMD ["python3", "-m", "AnonXMusic"]
