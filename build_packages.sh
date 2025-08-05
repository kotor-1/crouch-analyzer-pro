#!/bin/bash
# Install Pillow from binary wheel to avoid compilation issues
pip install Flask==3.0.0 gunicorn==21.2.0
pip install --no-binary :all: --only-binary Pillow Pillow==9.5.0
