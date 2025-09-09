#!/usr/bin/env bash

set -e  # Exit on any error

echo "Starting optimized build process for Render..."

# Update package list
echo "Updating package list..."
apt-get update -qq

# Install essential packages including build tools
echo "Installing essential packages and build tools..."
apt-get install -y -qq \
    wget \
    unzip \
    curl \
    gnupg \
    ca-certificates \
    build-essential \
    python3-dev \
    gcc \
    g++

# Install pre-built wheels to avoid compilation
echo "Installing Python packages with pre-built wheels..."
pip install --upgrade pip setuptools wheel

# Install packages in specific order to avoid conflicts
pip install numpy==1.24.3
pip install pandas==1.5.3
pip install pytz==2023.3
pip install plotly==5.15.0
pip install selenium==4.15.0
pip install streamlit==1.28.0

# Add Google signing key and repository
echo "Adding Google Chrome repository..."
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Update package list with new repo
apt-get update -qq

# Install Google Chrome (stable version)
echo "Installing Google Chrome..."
apt-get install -y -qq google-chrome-stable

# Get Chrome version for compatible ChromeDriver
echo "Detecting Chrome version..."
CHROME_VERSION=$(google-chrome --version | grep -oP "\d+\.\d+\.\d+")
CHROME_MAJOR_VERSION=$(echo $CHROME_VERSION | cut -d. -f1)

echo "Chrome version detected: $CHROME_VERSION (Major: $CHROME_MAJOR_VERSION)"

# Download and install compatible ChromeDriver
echo "Installing ChromeDriver..."
CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR_VERSION}")

if [ -z "$CHROMEDRIVER_VERSION" ]; then
    echo "Specific version not found, trying latest..."
    CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
fi

echo "Downloading ChromeDriver version: $CHROMEDRIVER_VERSION"
wget -q -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"

# Extract and install ChromeDriver
unzip -q /tmp/chromedriver.zip -d /tmp/
mv /tmp/chromedriver /usr/local/bin/chromedriver
chmod +x /usr/local/bin/chromedriver

# Verify installations
echo "Verifying installations..."
google-chrome --version
chromedriver --version
python3 -c "import pandas, streamlit, selenium, plotly; print('All packages imported successfully')"

# Clean up
echo "Cleaning up..."
apt-get clean
rm -rf /var/lib/apt/lists/*
rm -f /tmp/chromedriver.zip
rm -f /tmp/chromedriver

# Create startup script
echo "Creating startup script..."
cat > start.sh << 'EOF'
#!/bin/bash
export CHROME_BIN=/usr/bin/google-chrome-stable
export CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
export DISPLAY=:99
export PYTHONUNBUFFERED=1

# Start Streamlit with optimized settings
streamlit run SilverAutoCheck_ui.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
EOF

chmod +x start.sh
chmod +x build.sh

echo "Build completed successfully!"
echo "Chrome and ChromeDriver are ready for Selenium automation"
