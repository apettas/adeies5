.PHONY: help build up down logs shell migrate collectstatic createsuperuser backup restore clean

# Docker Compose v2 (docker compose) ή v1 (docker-compose)
ifneq (,$(shell docker compose version >/dev/null 2>&1 && echo ok))
  DOCKER_COMPOSE := docker compose
else
  DOCKER_COMPOSE := docker-compose
endif

COMPOSE_DEV := $(DOCKER_COMPOSE)
COMPOSE_PROD := $(DOCKER_COMPOSE) -f docker-compose.prod.yml

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
	@echo "  prod-build     - Build production images"
	@echo "  prod-up        - Start production services"
	@echo "  prod-down      - Stop production services"
	@echo "  prod-logs      - Show production logs"
	@echo "  prod-migrate   - Run production database migrations"
	@echo "  prod-backup    - Backup database (SQL only, ./backups)"
	@echo "  prod-backup-full - Full local backup (DB + media + config)"
	@echo "  disk-report    - Email disk usage report to ALERT_EMAIL"
	@echo "  monitoring-setup - Configure Netdata email + fail2ban on host VM"

# Development commands
build:
	$(COMPOSE_DEV) build

up:
	$(COMPOSE_DEV) up -d

down:
	$(COMPOSE_DEV) down

logs:
	$(COMPOSE_DEV) logs -f

shell:
	$(COMPOSE_DEV) exec web python manage.py shell

bash:
	$(COMPOSE_DEV) exec web bash

migrate:
	$(COMPOSE_DEV) exec web python fix_migrations.py

fix-migrations:
	$(COMPOSE_DEV) exec web python fix_migrations.py

collectstatic:
	$(COMPOSE_DEV) exec web python manage.py collectstatic --noinput

createsuperuser:
	$(COMPOSE_DEV) exec web python manage.py createsuperuser

# Database operations
backup:
	@echo "Creating database backup..."
	$(COMPOSE_DEV) exec db pg_dump -U pdede_user pdede_leaves > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup created successfully"

restore:
	@read -p "Enter backup file name: " backup_file; \
	$(COMPOSE_DEV) exec -T db psql -U pdede_user pdede_leaves < $$backup_file

# Cleanup
clean:
	$(COMPOSE_DEV) down -v
	docker system prune -f

# Production commands
prod-build:
	$(COMPOSE_PROD) build

prod-up:
	$(COMPOSE_PROD) up -d

prod-down:
	$(COMPOSE_PROD) down

prod-logs:
	$(COMPOSE_PROD) logs -f

prod-migrate:
	$(COMPOSE_PROD) exec web python manage.py migrate --noinput

monitoring-setup:
	bash monitoring/setup.sh

prod-backup:
	$(COMPOSE_PROD) --profile backup run backup

prod-backup-full:
	@bash scripts/backup-local.sh

disk-report:
	@bash scripts/disk-report.sh

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
	$(COMPOSE_DEV) exec web python manage.py test

# Check services status
status:
	$(COMPOSE_DEV) ps

# View container resource usage
stats:
	docker stats
