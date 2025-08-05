#!/bin/bash
python -m gunicorn app:app --timeout 120 --workers 1 --threads 2
