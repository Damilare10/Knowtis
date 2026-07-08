.PHONY: up down logs ps migrate test shell build clean help

# Default target.
help:
	@echo "Knowtis local-dev targets:"
	@echo "  make up        Build and start the full stack (creates backend/.env if missing)"
	@echo "  make down      Stop and remove containers (keeps the postgres volume)"
	@echo "  make logs      Tail logs for all services"
	@echo "  make ps        Show container status"
	@echo "  make migrate   Create/verify database tables (SQLAlchemy create_all)"
	@echo "  make test      Run the pytest suite inside the api container"
	@echo "  make shell     Drop into a bash shell in the api container"
	@echo "  make build     Rebuild images without cache"
	@echo "  make clean     Remove containers AND the postgres data volume (destructive)"

# Bring the stack up. Ensures backend/.env exists from the example first.
up:
	@if [ ! -f backend/.env ]; then \
		cp backend/.env.example backend/.env; \
		echo "Created backend/.env from backend/.env.example"; \
	fi
	docker compose up -d --buildwhich 

# Stop and remove containers (preserves the postgres data volume).
down:
	docker compose down

# Tail logs (Ctrl-C to detach).
logs:
	docker compose logs -f

ps:
	docker compose ps

# The app creates tables via SQLAlchemy Base.metadata.create_all on startup
# (see app/main.py lifespan). This target makes that explicit/idempotent so it
# can be re-run on demand. Swap for `alembic upgrade head` once migrations land.
migrate:
	docker compose exec api python -c "from app.database import engine, Base; import app.models; Base.metadata.create_all(bind=engine); print('tables OK')"

# Run the pytest suite inside the running api container.
test:
	docker compose exec api pytest -q

shell:
	docker compose exec api bash

# Rebuild images without the layer cache.
build:
	docker compose build --no-cache

# Destructive: remove containers and the postgres data volume.
clean:
	docker compose down -v
