# Use official Playwright Python image which includes all required browser dependencies
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set the working directory
WORKDIR /app

# Install Node.js (required for the Express server)
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy package.json and install Node.js dependencies
COPY package*.json ./
RUN npm install

# Copy requirements.txt and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright chromium browser specifically
RUN playwright install chromium

# Copy the rest of the application code
COPY . .

# Expose the port (Render sets the PORT environment variable)
EXPOSE 4000

# Start the Node.js Express server
CMD ["npm", "start"]
