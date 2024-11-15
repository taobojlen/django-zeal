install-hooks:
	git config core.hooksPath hooks/

install:
	$(MAKE) install-hooks
	uv pip compile requirements-dev.in -o requirements-dev.txt && uv pip sync requirements-dev.txt

ci:
	pip install -r requirements-dev.txt

test:
	pytest -s --tb=native --random-order -m "not benchmark" $(ARGS)

benchmark:
	pytest -s $(ARGS) --codspeed

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
