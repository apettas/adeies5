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
echo "Creating superuser if needed..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='admin@pdede.gr').exists():
    User.objects.create_superuser(
        email='admin@pdede.gr',
        first_name='Admin',
        last_name='ΠΔΕΔΕ',
        password='admin123'
    )
    print('Superuser created successfully')
else:
    print('Superuser already exists')
EOF

# Load initial data if needed
echo "Loading initial data..."
python manage.py loaddata --ignorenonexistent initial_data.json || echo "No initial data to load"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the application
echo "Starting application..."
exec "$@"