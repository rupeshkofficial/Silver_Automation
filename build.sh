#!/usr/bin/env bash

# Update package list and install Chrome + ChromeDriver
apt-get update
apt-get install -y wget unzip curl gnupg

# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt install -y ./google-chrome-stable_current_amd64.deb

# Install ChromeDriver (matching Chrome version)
CHROME_VERSION=$(google-chrome --version | grep -oP "\d+\.\d+\.\d+" | head -1)
CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}" || curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"
unzip /tmp/chromedriver.zip -d /usr/local/bin/
chmod +x /usr/local/bin/chromedriver
