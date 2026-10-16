#!/bin/sh
set -e

# Prepare the app only when starting the web server.
if [ "$1" = "gunicorn" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
fi

# Execute the command supplied by Docker.
exec "$@"