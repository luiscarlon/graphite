.PHONY: sync seed test lint typecheck fmt app clean

seed:
	uv run refsite-generate

sync:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy packages --exclude tests

app:
	uv run streamlit run packages/app/src/app/main.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
