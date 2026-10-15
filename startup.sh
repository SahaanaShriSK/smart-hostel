#!/bin/bash
set -e
cd /home/site/wwwroot
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
