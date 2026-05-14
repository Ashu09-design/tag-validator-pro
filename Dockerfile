FROM python:3.10

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up environment variables for Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/app/ms-playwright

WORKDIR /app

# Copy application files
COPY . .

# Install Node modules
RUN npm install

# Install Python dependencies globally
RUN pip install --no-cache-dir pandas openpyxl playwright playwright-stealth

# Install Playwright browser and system dependencies into the specific path
RUN playwright install-deps chromium \
    && playwright install chromium

# Set up Hugging Face non-root user permissions
RUN useradd -m -u 1000 user
RUN chown -R user:user /app

USER user

ENV PORT=7860
EXPOSE 7860

CMD ["npm", "start"]
