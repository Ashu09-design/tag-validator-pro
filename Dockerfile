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

# Copy all files and set ownership to user
COPY --chown=user:user . .

# Change ownership of /app
RUN chown -R user:user /app

# Switch to non-root user (Required for Hugging Face Spaces)
USER user

# Install Node modules
RUN npm install

# Create a virtual environment with system packages and install Python deps
ENV VIRTUAL_ENV=/app/venv
RUN python3 -m venv --system-site-packages $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Create uploads directory
RUN mkdir -p uploads

# Set environment variables for Hugging Face
ENV PORT=7860
EXPOSE 7860

# Start the server
CMD ["npm", "start"]
