.PHONY: help build push deploy test lint clean all

# ============================================
# Variables
# ============================================
VERSION ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "latest")
REGISTRY ?= ghcr.io/your-org
IMAGE_PREFIX ?= sns-monitor
NAMESPACE ?= platform
KUBECONFIG_DEV ?= ~/.kube/config
KUBECONFIG_PROD ?= ~/.kube/config

# Image names
IMAGES = api-backend frontend youtube-crawler dcinside-crawler llm-analyzer auth-service

# ============================================
# Help
# ============================================
help:
	@echo "SNS Monitoring System - Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make build              - Build all Docker images"
	@echo "  make build-<service>    - Build specific service (api-backend, frontend, etc.)"
	@echo "  make push               - Push all images to ghcr.io"
	@echo "  make push-<service>     - Push specific service"
	@echo "  make deploy-dev         - Deploy to dev-cluster"
	@echo "  make deploy-prod        - Deploy to prod-cluster"
	@echo "  make dry-run-dev        - Helm dry-run for dev"
	@echo "  make lint               - Lint Helm chart"
	@echo "  make test               - Run tests"
	@echo "  make clean              - Clean up"
	@echo ""
	@echo "Variables:"
	@echo "  VERSION=$(VERSION)"
	@echo "  REGISTRY=$(REGISTRY)"

# ============================================
# GitHub Container Registry Login
# ============================================
ghcr-login:
	@echo "🔐 Logging in to GitHub Container Registry..."
	@echo "$(GITHUB_TOKEN)" | docker login ghcr.io -u $(GITHUB_USER) --password-stdin

# ============================================
# Build
# ============================================
build: build-api-backend build-frontend build-youtube-crawler build-dcinside-crawler build-llm-analyzer
	@echo "✅ All images built!"

build-api-backend:
	@echo "🔨 Building api-backend..."
	docker build -t $(REGISTRY)/$(IMAGE_PREFIX)-api-backend:$(VERSION) -f docker/Dockerfile.api .
	docker tag $(REGISTRY)/$(IMAGE_PREFIX)-api-backend:$(VERSION) $(REGISTRY)/$(IMAGE_PREFIX)-api-backend:latest

build-frontend:
	@echo "🔨 Building frontend..."
	docker build -t $(REGISTRY)/$(IMAGE_PREFIX)-frontend:$(VERSION) -f docker/Dockerfile.frontend ./frontend
	docker tag $(REGISTRY)/$(IMAGE_PREFIX)-frontend:$(VERSION) $(REGISTRY)/$(IMAGE_PREFIX)-frontend:latest

build-youtube-crawler:
	@echo "🔨 Building youtube-crawler..."
	docker build -t $(REGISTRY)/$(IMAGE_PREFIX)-youtube-crawler:$(VERSION) -f docker/Dockerfile.youtube-crawler .
	docker tag $(REGISTRY)/$(IMAGE_PREFIX)-youtube-crawler:$(VERSION) $(REGISTRY)/$(IMAGE_PREFIX)-youtube-crawler:latest

build-dcinside-crawler:
	@echo "🔨 Building dcinside-crawler..."
	docker build -t $(REGISTRY)/$(IMAGE_PREFIX)-dcinside-crawler:$(VERSION) -f docker/Dockerfile.crawler .
	docker tag $(REGISTRY)/$(IMAGE_PREFIX)-dcinside-crawler:$(VERSION) $(REGISTRY)/$(IMAGE_PREFIX)-dcinside-crawler:latest

build-llm-analyzer:
	@echo "🔨 Building llm-analyzer..."
	docker build -t $(REGISTRY)/$(IMAGE_PREFIX)-llm-analyzer:$(VERSION) -f docker/Dockerfile.analyzer .
	docker tag $(REGISTRY)/$(IMAGE_PREFIX)-llm-analyzer:$(VERSION) $(REGISTRY)/$(IMAGE_PREFIX)-llm-analyzer:latest

build-auth-service:
	@echo "🔨 Building auth-service..."
	docker build -t $(REGISTRY)/$(IMAGE_PREFIX)-auth-service:$(VERSION) -f docker/Dockerfile.api .
	docker tag $(REGISTRY)/$(IMAGE_PREFIX)-auth-service:$(VERSION) $(REGISTRY)/$(IMAGE_PREFIX)-auth-service:latest

# ============================================
# Push
# ============================================
push: push-api-backend push-frontend push-youtube-crawler push-dcinside-crawler push-llm-analyzer
	@echo "✅ All images pushed!"

push-api-backend: build-api-backend
	@echo "📤 Pushing api-backend..."
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-api-backend:$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-api-backend:latest

push-frontend: build-frontend
	@echo "📤 Pushing frontend..."
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-frontend:$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-frontend:latest

push-youtube-crawler: build-youtube-crawler
	@echo "📤 Pushing youtube-crawler..."
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-youtube-crawler:$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-youtube-crawler:latest

push-dcinside-crawler: build-dcinside-crawler
	@echo "📤 Pushing dcinside-crawler..."
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-dcinside-crawler:$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-dcinside-crawler:latest

push-llm-analyzer: build-llm-analyzer
	@echo "📤 Pushing llm-analyzer..."
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-llm-analyzer:$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-llm-analyzer:latest

# ============================================
# Helm
# ============================================
helm-deps:
	@echo "📦 Updating Helm dependencies..."
	helm dependency update ./helm/sns-monitor

lint: helm-deps
	@echo "🔍 Linting Helm chart..."
	helm lint ./helm/sns-monitor
	@echo "✅ Lint passed!"

dry-run-dev: helm-deps
	@echo "🔍 Helm dry-run (dev)..."
	KUBECONFIG=$(KUBECONFIG_DEV) helm upgrade --install sns-monitor ./helm/sns-monitor \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--set global.imageRegistry=$(REGISTRY) \
		--dry-run

dry-run-prod: helm-deps
	@echo "🔍 Helm dry-run (prod)..."
	KUBECONFIG=$(KUBECONFIG_PROD) helm upgrade --install sns-monitor ./helm/sns-monitor \
		--namespace $(NAMESPACE) \
		--create-namespace \
		-f ./helm/sns-monitor/values-production.yaml \
		--set global.imageRegistry=$(REGISTRY) \
		--dry-run

# ============================================
# Deploy
# ============================================
deploy-dev: helm-deps
	@echo "🚀 Deploying to dev-cluster..."
	KUBECONFIG=$(KUBECONFIG_DEV) helm upgrade --install sns-monitor ./helm/sns-monitor \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--set global.imageRegistry=$(REGISTRY) \
		--wait --timeout 10m
	@echo "✅ Deployed to dev-cluster!"

deploy-prod: helm-deps
	@echo "🚀 Deploying to prod-cluster..."
	KUBECONFIG=$(KUBECONFIG_PROD) helm upgrade --install sns-monitor ./helm/sns-monitor \
		--namespace $(NAMESPACE) \
		--create-namespace \
		-f ./helm/sns-monitor/values-production.yaml \
		--set global.imageRegistry=$(REGISTRY) \
		--wait --timeout 10m
	@echo "✅ Deployed to prod-cluster!"

# ============================================
# Status
# ============================================
status-dev:
	@echo "📊 Status (dev-cluster)..."
	KUBECONFIG=$(KUBECONFIG_DEV) kubectl get pods -n $(NAMESPACE)
	KUBECONFIG=$(KUBECONFIG_DEV) kubectl get svc -n $(NAMESPACE)

status-prod:
	@echo "📊 Status (prod-cluster)..."
	KUBECONFIG=$(KUBECONFIG_PROD) kubectl get pods -n $(NAMESPACE)
	KUBECONFIG=$(KUBECONFIG_PROD) kubectl get svc -n $(NAMESPACE)

# ============================================
# Test
# ============================================
test:
	@echo "🧪 Running tests..."
	cd crawlers/youtube && python -m pytest -v || true
	cd crawlers/dcinside && python -m pytest -v || true
	@echo "✅ Tests complete!"

test-local:
	@echo "🧪 Running local docker-compose..."
	docker-compose up -d
	@echo "⏳ Waiting for services..."
	sleep 10
	docker-compose ps
	@echo "✅ Local environment ready!"

# ============================================
# Clean
# ============================================
clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v 2>/dev/null || true
	docker rmi $(REGISTRY)/$(IMAGE_PREFIX)-api-backend:$(VERSION) 2>/dev/null || true
	docker rmi $(REGISTRY)/$(IMAGE_PREFIX)-frontend:$(VERSION) 2>/dev/null || true
	docker rmi $(REGISTRY)/$(IMAGE_PREFIX)-youtube-crawler:$(VERSION) 2>/dev/null || true
	docker rmi $(REGISTRY)/$(IMAGE_PREFIX)-dcinside-crawler:$(VERSION) 2>/dev/null || true
	docker rmi $(REGISTRY)/$(IMAGE_PREFIX)-llm-analyzer:$(VERSION) 2>/dev/null || true
	@echo "✅ Cleaned!"

# ============================================
# All
# ============================================
all: lint build push deploy-dev
	@echo "🎉 All done!"
