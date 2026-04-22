.PHONY: build up down logs dev format

# Docker Compose commands
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# Local Development Commands
dev:
	source venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000

format:
	source venv/bin/activate && autopep8 --in-place --aggressive --aggressive *.py
