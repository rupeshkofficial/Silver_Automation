#!/usr/bin/env bash
# Update package list and install Chrome + ChromeDriver for Render
apt-get update
apt-get install -y wget unzip curl gnupg python3-pip

# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -yf
apt-get install -y -f
rm -f google-chrome-stable_current_amd64.deb

# Install ChromeDriver (fixed version)
CHROMEDRIVER_VERSION="114.0.5735.90"
wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"
unzip /tmp/chromedriver.zip -d /usr/local/bin/
chmod +x /usr/local/bin/chromedriver
rm -f /tmp/chromedriver.zip

# Install additional dependencies
apt-get install -y libnss3-dev libgconf-2-4 libxss1 libappindicator1 libindicator7

# Verify installations
echo "Chrome version:"
google-chrome --version
echo "ChromeDriver version:"
chromedriver --version

# Install Python dependencies
pip3 install --upgrade pip
pip3 install -r requirements.txt
