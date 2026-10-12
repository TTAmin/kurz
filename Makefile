.PHONY: install lint test run up down kind-up deploy smoke kind-down

IMAGE ?= kurz:dev

install:
	python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

lint:
	ruff check . && ruff format --check .

test:
	pytest --cov --cov-report=term-missing

run:
	uvicorn app.main:create_app --factory --reload

up:
	docker compose up --build -d

down:
	docker compose down

kind-up:
	kind create cluster --name kurz

deploy:
	docker build -t $(IMAGE) .
	kind load docker-image $(IMAGE) --name kurz
	helm upgrade --install kurz deploy/helm/kurz \
		--set image.repository=kurz,image.tag=dev,image.pullPolicy=Never --wait

smoke:
	scripts/smoke-test.sh $(or $(URL),http://localhost:8000)

kind-down:
	kind delete cluster --name kurz
