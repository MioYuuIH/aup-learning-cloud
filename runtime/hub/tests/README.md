# RemoteLab Hub Tests

Simple unit tests for `RemoteLabKubeSpawner` component.

## Quick Start

### Install Test Dependencies

```bash
cd /home/kerwin/aup-learning-cloud
pip install pytest pytest-cov pytest-mock
```

### Run Tests

```bash
# Run all tests
pytest runtime/hub/tests/ -v

# Run with coverage report
pytest runtime/hub/tests/ -v --cov=runtime.hub.core.spawner --cov-report=html

# Run only unit tests
pytest runtime/hub/tests/ -v -m unit

# Run specific test class
pytest runtime/hub/tests/test_kubernetes_spawner.py::TestParseMemoryString -v

# Run with detailed output
pytest runtime/hub/tests/ -vv -s
```

## Test Structure

```
runtime/hub/tests/
├── __init__.py                      # Package marker
├── pytest.ini                       # Pytest configuration
├── conftest.py                      # Shared fixtures and configuration
└── test_kubernetes_spawner.py       # Unit tests
```

## Fixtures Available

### `mock_hub_config`
Mock `HubConfig` with test settings:
- Resource images (pytorch, tensorflow, tutorial)
- Resource requirements (CPU, memory, GPU)
- Team resource mapping
- Quota rates (10, 100, 150)

### `mock_spawner`
Mock `RemoteLabKubeSpawner` instance with actual methods:
- `_parse_memory_string()`
- `get_quota_rate()`

### `mock_user`
Mock JupyterHub user with:
- `name = "test-user"`
- `auth_state` with GitHub access token

### `mock_quota_manager`
Mock `QuotaManager` for quota testing

## Test Coverage

### Unit Tests (17 tests)

#### TestParseMemoryString (10 tests)
- ✅ Parse Kubernetes formats: Gi, Mi, G, M, Ti, T
- ✅ Parse numeric inputs: int, float
- ✅ Handle invalid formats
- ✅ Handle whitespace

**Example**:
```python
def test_parse_gi_format(self, mock_spawner):
    result = mock_spawner._parse_memory_string("4Gi")
    assert result == 4.0
```

#### TestGetQuotaRate (6 tests)
- ✅ Lookup rates for: cpu, gpu, npu
- ✅ Handle unknown accelerator types
- ✅ Handle None/empty values

**Example**:
```python
def test_quota_rate_gpu(self, mock_spawner):
    rate = mock_spawner.get_quota_rate("gpu")
    assert rate == 100
```

#### TestOptionsFromForm (4 tests)
- ✅ Parse valid form data
- ✅ Validate resource types
- ✅ Error on multiple resource selection
- ✅ Parse custom runtime values

**Example**:
```python
def test_valid_resource_selection(self):
    spawner = RemoteLabKubeSpawner()
    formdata = {
        "runtime": ["20"],
        "resource_type": ["pytorch"],
    }
    options = spawner.options_from_form(formdata)
    assert options["runtime_minutes"] == 20
```

#### TestResourceConfiguration (4 tests)
- ✅ Verify resource images configured
- ✅ Verify resource requirements
- ✅ Verify team mapping
- ✅ Verify quota rates

#### TestConfigureFromConfig (1 test)
- ✅ Class method sets all configuration

#### TestMemoryCalculations (2 tests)
- ✅ Common memory conversion scenarios
- ✅ Quota rate hierarchy validation

## Sample Test Run Output

```
$ pytest runtime/hub/tests/ -v

tests/test_kubernetes_spawner.py::TestParseMemoryString::test_parse_int_input PASSED
tests/test_kubernetes_spawner.py::TestParseMemoryString::test_parse_gi_format PASSED
tests/test_kubernetes_spawner.py::TestParseMemoryString::test_parse_mi_format PASSED
tests/test_kubernetes_spawner.py::TestGetQuotaRate::test_quota_rate_cpu PASSED
tests/test_kubernetes_spawner.py::TestGetQuotaRate::test_quota_rate_gpu PASSED
tests/test_kubernetes_spawner.py::TestOptionsFromForm::test_valid_resource_selection PASSED
tests/test_kubernetes_spawner.py::TestOptionsFromForm::test_invalid_resource_type PASSED
...

======================== 28 passed in 0.45s ========================
```

## Running with Coverage

```bash
pytest runtime/hub/tests/ --cov=runtime.hub.core --cov-report=html --cov-report=term-missing
```

This will:
1. Run all tests
2. Generate HTML coverage report in `htmlcov/`
3. Show coverage summary in terminal

## What's NOT Tested (Complex Components)

These require mocking external dependences (K8s, GitHub, DB):

- `start()` - Async pod creation + quota checks
- `stop()` - Async cleanup + quota settlement
- `check_timeout()` - Timer scheduling
- `get_user_teams()` - GitHub API calls
- `_configure_spawner()` - Full K8s pod spec configuration

See `tests/conftest.py` for fixture setup to extend these tests.

## Next Steps

To extend testing:

1. **Mock GitHub API**: Test `get_user_teams()` with different auth modes
2. **Mock Kubernetes**: Test `_configure_spawner()` pod spec generation
3. **Mock Database**: Test quota checks in `start()` and `stop()`
4. **Integration Tests**: Full workflow with all mocking

Example fixture expansion in the TODO comments in `conftest.py`.

## Troubleshooting

### ImportError: "No module named 'core'"
Ensure you're running pytest from the workspace root or have `PYTHONPATH` set:
```bash
export PYTHONPATH=/home/kerwin/aup-learning-cloud/runtime/hub:$PYTHONPATH
pytest tests/ -v
```

### "conftest.py not found"
Make sure you're running from the correct directory:
```bash
cd /home/kerwin/aup-learning-cloud
pytest runtime/hub/tests/ -v
```

### Mock object not callable
Ensure you're using `spec` parameter when creating mocks:
```python
spawner = Mock(spec=RemoteLabKubeSpawner)
```

