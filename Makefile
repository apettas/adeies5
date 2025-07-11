.PHONY: help build up down logs shell migrate collectstatic createsuperuser backup restore clean

# Default target
help:
	@echo "Available commands:"
	@echo "  build          - Build Docker images"
	@echo "  up             - Start all services"
	@echo "  down           - Stop all services"
	@echo "  logs           - Show logs"
	@echo "  shell          - Open Django shell"
	@echo "  bash           - Open bash shell in web container"
	@echo "  migrate        - Run database migrations"
	@echo "  fix-migrations - Fix migration conflicts"
	@echo "  collectstatic  - Collect static files"
	@echo "  createsuperuser- Create Django superuser"
	@echo "  backup         - Backup database"
	@echo "  restore        - Restore database from backup"
	@echo "  clean          - Clean up containers and volumes"
	@echo "  prod-up        - Start production services"
	@echo "  prod-down      - Stop production services"
	@echo "  prod-logs      - Show production logs"

# Development commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker-compose exec web python manage.py shell

bash:
	docker-compose exec web bash

migrate:
	docker-compose exec web python fix_migrations.py

fix-migrations:
	docker-compose exec web python fix_migrations.py

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

# Database operations
backup:
	@echo "Creating database backup..."
	docker-compose exec db pg_dump -U pdede_user pdede_leaves > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup created successfully"

restore:
	@read -p "Enter backup file name: " backup_file; \
	docker-compose exec -T db psql -U pdede_user pdede_leaves < $$backup_file

# Cleanup
clean:
	docker-compose down -v
	docker system prune -f

# Production commands
prod-build:
	docker-compose -f docker-compose.prod.yml build

prod-up:
	docker-compose -f docker-compose.prod.yml up -d

prod-down:
	docker-compose -f docker-compose.prod.yml down

prod-logs:
	docker-compose -f docker-compose.prod.yml logs -f

prod-backup:
	docker-compose -f docker-compose.prod.yml --profile backup run backup

# Development workflow
dev-setup: build up migrate collectstatic
	@echo "Development environment is ready!"
	@echo "Access the application at: http://localhost:8000"
	@echo "Admin panel: http://localhost:8000/admin"
	@echo "Default credentials: admin@pdede.gr / admin123"

# Production workflow
prod-setup: prod-build prod-up
	@echo "Production environment is ready!"
	@echo "Don't forget to configure SSL certificates and update .env file"

# Testing
test:
	docker-compose exec web python manage.py test

# Check services status
status:
	docker-compose ps

# View container resource usage
stats:
	docker stats