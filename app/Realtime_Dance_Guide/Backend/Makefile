# Django Management Commands Shortcuts

.PHONY: help install migrate makemigrations createsuperuser run test lint format clean

help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make migrate        - Run database migrations"
	@echo "  make makemigrations - Create new migrations"
	@echo "  make createsuperuser- Create Django superuser"
	@echo "  make run            - Run development server"
	@echo "  make test           - Run tests"
	@echo "  make lint           - Run linting"
	@echo "  make format         - Format code with black"
	@echo "  make clean          - Remove Python cache files"

install:
	pip install -r requirements.txt

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

createsuperuser:
	python manage.py createsuperuser

run:
	python manage.py runserver

test:
	pytest

lint:
	flake8 .
	pylint --load-plugins pylint_django --django-settings-module=Backend.settings Backend/ users/ api/ core/

format:
	black --line-length 120 .
	isort .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

collectstatic:
	python manage.py collectstatic --noinput

shell:
	python manage.py shell
