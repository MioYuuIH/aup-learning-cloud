.PHONY: test test-verbose test-coverage test-quick test-watch test-shell docker-build-test docker-clean

# Colors for output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# Test Docker image name
TEST_IMAGE := auplc-test
TEST_CONTAINER := auplc-test-run

# ============================================================
# Main Test Target - Run tests in Docker
# ============================================================
.PHONY: test
test: docker-build-test
	@echo "$(CYAN)▶ Running tests in Docker container...$(NC)"
	docker run --rm \
		--name $(TEST_CONTAINER) \
		$(TEST_IMAGE) \
		pytest runtime/hub/tests/ -v

# ============================================================
# Test Variants
# ============================================================

# Run tests with verbose output and show print statements
.PHONY: test-verbose
test-verbose: docker-build-test
	@echo "$(CYAN)▶ Running tests with verbose output...$(NC)"
	docker run --rm \
		--name $(TEST_CONTAINER) \
		$(TEST_IMAGE) \
		pytest runtime/hub/tests/ -vv -s

# Run tests with coverage report
.PHONY: test-coverage
test-coverage: docker-build-test
	@echo "$(CYAN)▶ Running tests with coverage report...$(NC)"
	docker run --rm \
		-v "$(PWD)/htmlcov:/app/htmlcov" \
		--name $(TEST_CONTAINER) \
		$(TEST_IMAGE) \
		pytest runtime/hub/tests/ -v \
			--cov=runtime.hub.core \
			--cov-report=html \
			--cov-report=term-missing
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/index.html$(NC)"

# Run a quick subset of tests (only fast unit tests)
.PHONY: test-quick
test-quick: docker-build-test
	@echo "$(CYAN)▶ Running quick tests only...$(NC)"
	docker run --rm \
		--name $(TEST_CONTAINER) \
		$(TEST_IMAGE) \
		pytest runtime/hub/tests/test_kubernetes_spawner.py::TestParseMemoryString \
			runtime/hub/tests/test_kubernetes_spawner.py::TestGetQuotaRate \
			-v

# Run specific test class/method
.PHONY: test-specific
test-specific: docker-build-test
	@echo "$(CYAN)▶ Running specific test: $(TEST)$(NC)"
	docker run --rm \
		--name $(TEST_CONTAINER) \
		$(TEST_IMAGE) \
		pytest $(TEST) -v

# Stop running tests
.PHONY: test-stop
test-stop:
	@echo "$(YELLOW)⊘ Stopping test container...$(NC)"
	docker kill $(TEST_CONTAINER) 2>/dev/null || echo "No running container"

# ============================================================
# Docker Build Targets
# ============================================================

# Build test Docker image
.PHONY: docker-build-test
docker-build-test:
	@echo "$(CYAN)▶ Building test Docker image: $(TEST_IMAGE)$(NC)"
	docker build \
		-f Dockerfile.test \
		-t $(TEST_IMAGE) \
		--progress=plain \
		.
	@echo "$(GREEN)✓ Test image built: $(TEST_IMAGE)$(NC)"

# Rebuild test image (clean build)
.PHONY: docker-rebuild-test
docker-rebuild-test:
	@echo "$(YELLOW)⊘ Removing old test image...$(NC)"
	docker rmi -f $(TEST_IMAGE) 2>/dev/null || true
	@make docker-build-test

# Show test image info
.PHONY: docker-inspect-test
docker-inspect-test:
	docker inspect $(TEST_IMAGE)

# ============================================================
# Cleanup Targets
# ============================================================

# Clean up test images and containers
.PHONY: docker-clean
docker-clean:
	@echo "$(YELLOW)⊘ Cleaning up test containers and images...$(NC)"
	docker rm -f $(TEST_CONTAINER) 2>/dev/null || true
	docker rmi -f $(TEST_IMAGE) 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

# Clean coverage reports
.PHONY: clean-coverage
clean-coverage:
	@echo "$(YELLOW)⊘ Removing coverage reports...$(NC)"
	rm -rf htmlcov .coverage
	@echo "$(GREEN)✓ Coverage reports removed$(NC)"

# Full clean
.PHONY: clean
clean: docker-clean clean-coverage
	@echo "$(GREEN)✓ Full cleanup complete$(NC)"

# ============================================================
# Help Target
# ============================================================

.PHONY: help
help:
	@echo "$(CYAN)AUP Learning Cloud - Test Command Reference$(NC)"
	@echo ""
	@echo "$(GREEN)Main Commands:$(NC)"
	@echo "  make test              - Run all tests in Docker container"
	@echo "  make test-verbose      - Run tests with verbose output & print statements"
	@echo "  make test-coverage     - Run tests and generate coverage report"
	@echo "  make test-quick        - Run only fast unit tests"
	@echo "  make test-specific     - Run specific test: make test-specific TEST=runtime/hub/tests/test_kubernetes_spawner.py::TestParseMemoryString"
	@echo ""
	@echo "$(GREEN)Docker Commands:$(NC)"
	@echo "  make docker-build-test - Build test Docker image"
	@echo "  make docker-rebuild-test - Rebuild test image (clean)"
	@echo "  make docker-inspect-test - Inspect test image details"
	@echo "  make test-stop         - Stop running test container"
	@echo ""
	@echo "$(GREEN)Cleanup Commands:$(NC)"
	@echo "  make clean             - Remove all test artifacts"
	@echo "  make docker-clean      - Remove test containers & images only"
	@echo "  make clean-coverage    - Remove coverage reports only"
	@echo ""
	@echo "$(GREEN)Example Usage:$(NC)"
	@echo "  make test                                    # Run all tests"
	@echo "  make test-coverage                           # Run with coverage report"
	@echo "  make test-specific TEST=<test-path>::<name>  # Run specific test"
	@echo ""
