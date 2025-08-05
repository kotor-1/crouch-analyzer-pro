#!/bin/bash
# Python 3.11を明示的に使用
python3.11 -m pip install -r requirements.txt
python3.11 -m gunicorn app:app
