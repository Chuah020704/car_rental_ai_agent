.PHONY: install run ui index test lint format typecheck check docker-build docker-up docker-down

install:
	uv sync --all-extras

run:
	uv run uvicorn app_car_rental:app --reload --port 8081

ui:
	uv run streamlit run app/ui/streamlit_app.py

index:
	uv run python scripts/build_index.py --rebuild

test:
	uv run pytest -m "not llm"

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy app

check: lint typecheck test

docker-build:
	docker compose build

docker-up:
	docker compose up --build

docker-down:
	docker compose down
