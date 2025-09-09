#!/bin/bash

# Set Chrome environment variables
export CHROME_BIN=/usr/bin/google-chrome-stable
export CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
export DISPLAY=:99

# Optimize for Render environment
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Start Streamlit with optimized settings
streamlit run SilverAutoCheck_ui.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --server.maxUploadSize=10 \
    --server.maxMessageSize=10 \
    --browser.gatherUsageStats=false
