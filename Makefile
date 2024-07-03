install-hooks:
	git config core.hooksPath hooks/

install:
	$(MAKE) install-hooks
	uv pip compile requirements.in -o requirements.txt && uv pip compile requirements-dev.in -o requirements-dev.txt && uv pip install -r requirements.txt && uv pip install -r requirements-dev.txt

ci:
	pip install -r requirements.txt && pip install -r requirements-dev.txt

test:
	pytest -s --tb=native

format-check:
	ruff format --check && ruff check

format:
	ruff format && ruff check --fix

typecheck:
	pyright .

build:
	python -m build --installer uv

publish:
	twine upload dist/*
