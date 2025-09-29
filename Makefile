PYTHON=python
POETRY=poetry

.PHONY: up mig test lint

up:
	docker-compose up --build

mig:
	alembic revision --autogenerate -m "auto"
	alembic upgrade head

test:
	pytest

lint:
	ruff check
	black --check .
	mypy src

