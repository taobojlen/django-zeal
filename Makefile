install:
	uv pip compile requirements.in -o requirements.txt && uv pip compile requirements-dev.in -o requirements-dev.txt && uv pip install -r requirements.txt && uv pip install -r requirements-dev.txt

ci:
	pip install -r requirements.txt && pip install -r requirements-dev.txt

test:
	pytest -s

format:
	ruff format && ruff check --fix

typecheck:
	pyright .
