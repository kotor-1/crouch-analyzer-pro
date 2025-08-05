#!/bin/bash
# Install system dependencies for Pillow
apt-get update
apt-get install -y python3-dev zlib1g-dev libjpeg-dev libpng-dev

# Now install Python packages
poetry install
