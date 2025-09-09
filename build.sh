#!/usr/bin/env bash
# Update package list and install Chrome + ChromeDriver
sudo apt-get update
sudo apt-get install -y wget unzip curl gnupg python3-pip libnss3-dev libgconf-2-4 libxss1 libappindicator1 libindicator7

# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
rm -f google-chrome-stable_current_amd64.deb

# Install ChromeDriver (use fixed version instead of dynamic detection)
CHROMEDRIVER_VERSION="114.0.5735.90"  # Use a fixed version that works
wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"
sudo unzip /tmp/chromedriver.zip -d /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
rm -f /tmp/chromedriver.zip

# Verify installations
google-chrome --version
chromedriver --version

# Install Python dependencies
pip3 install -r requirements.txt
