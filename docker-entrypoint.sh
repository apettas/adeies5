#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done
echo "Database started"

# Fix any migration conflicts first
echo "Checking and fixing migration conflicts..."
python fix_migrations.py || echo "Migration fix completed with warnings"

# Create superuser if it doesn't exist
if [ "${CREATE_DEFAULT_SUPERUSER:-False}" = "True" ]; then
  if [ -z "$DJANGO_SUPERUSER_EMAIL" ] || [ -z "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "CREATE_DEFAULT_SUPERUSER=True requires DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD"
    exit 1
  fi

  echo "Creating configured superuser if needed..."
  python manage.py shell << EOF
import os
from django.contrib.auth import get_user_model

User = get_user_model()
email = os.environ["DJANGO_SUPERUSER_EMAIL"]
password = os.environ["DJANGO_SUPERUSER_PASSWORD"]
first_name = os.environ.get("DJANGO_SUPERUSER_FIRST_NAME", "Admin")
last_name = os.environ.get("DJANGO_SUPERUSER_LAST_NAME", "User")

if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password
    )
    print("Superuser created successfully")
else:
    print("Superuser already exists")
EOF
else
  echo "Skipping default superuser creation"
fi

# Load initial data if needed
echo "Loading initial data..."
python manage.py loaddata --ignorenonexistent initial_data.json || echo "No initial data to load"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the application
echo "Starting application..."
exec "$@"
