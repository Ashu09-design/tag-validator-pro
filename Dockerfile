# Use official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Install Node.js
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up a new user named "user" with user ID 1000
RUN useradd -m -u 1000 user

# Set working directory
WORKDIR /app

# Copy files and set ownership to user
COPY --chown=user:user package*.json ./
RUN npm install

COPY --chown=user:user requirements.txt ./
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Install browsers
RUN playwright install chromium

# Copy rest of the app
COPY --chown=user:user . .

# Create uploads directory and set permissions
RUN mkdir -p uploads && chown -R user:user /app

# Switch to non-root user (Required for Hugging Face Spaces)
USER user

# Set environment variables for Hugging Face
ENV PORT=7860
EXPOSE 7860

# Start the server
CMD ["npm", "start"]
