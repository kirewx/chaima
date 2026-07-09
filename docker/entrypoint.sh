#!/bin/sh
set -e

echo "Running database migrations..."
chaima db upgrade head

echo "Starting ChAiMa server on 0.0.0.0:8000..."
exec chaima run --host 0.0.0.0 --port 8000
