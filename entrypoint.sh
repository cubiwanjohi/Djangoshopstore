#!/bin/sh
set -e

# Prepare the app only when starting the web server.
if [ "$1" = "gunicorn" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput

    # Use Railway's assigned port, or 8000 locally.
    exec "$@" --bind "0.0.0.0:${PORT:-8000}"
fi

# Execute other commands normally.
exec "$@"
