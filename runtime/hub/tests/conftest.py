"""
Pytest configuration and fixtures for RemoteLab Hub tests
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from core.config import HubConfig


@pytest.fixture
def mock_hub_config():
    """Create a mock HubConfig with test settings."""
    config = Mock(spec=HubConfig)

    # Configuration attributes
    config.github_org_name = "test-org"
    config.auth_mode = "auto-login"
    config.single_node_mode = False
    config.quota_enabled = True

    # Resource configuration
    config.resource_images = {
        "pytorch": "amd-pytorch:latest",
        "tensorflow": "amd-tensorflow:latest",
        "tutorial": "tutorial-jupyter:latest",
    }

    config.resource_requirements = {
        "pytorch": {
            "cpu": "2",
            "memory": "4Gi",
            "amd.com/gpu": "1",
        },
        "tensorflow": {
            "cpu": "4",
            "memory": "8Gi",
            "amd.com/gpu": "2",
        },
        "tutorial": {
            "cpu": "1",
            "memory": "2Gi",
        },
    }

    config.accelerator_options = {
        "gpu-prochip": {
            "displayName": "AMD PROCHIP GPU",
            "quotaRate": 1.0,
        },
        "gpu-instinct": {
            "displayName": "AMD INSTINCT",
            "quotaRate": 1.5,
        },
    }

    # Permission mapping
    config.team_resource_mapping = {
        "official": ["pytorch", "tensorflow", "tutorial"],
        "backend": ["pytorch"],
        "native-users": ["tutorial"],
    }

    config.node_selector_mapping = {
        "gpu-prochip": {
            "gpu-type": "PROCHIP",
            "accelerator": "amd-gpu",
        }
    }

    config.environment_mapping = {
        "gpu-prochip": {
            "DEVICE": "gpu",
            "CUDA_VISIBLE_DEVICES": "0",
        }
    }

    # Quota settings
    config.quota_rates = {
        "cpu": 10,
        "gpu": 100,
        "npu": 150,
    }
    config.default_quota = 1000
    config.minimum_quota_to_start = 10

    return config


@pytest.fixture
def mock_spawner(mock_hub_config):
    """Create a mock RemoteLabKubeSpawner instance."""
    from core.spawner.kubernetes import RemoteLabKubeSpawner

    spawner = Mock(spec=RemoteLabKubeSpawner)

    # Copy config to spawner
    spawner.github_org_name = mock_hub_config.github_org_name
    spawner.auth_mode = mock_hub_config.auth_mode
    spawner.single_node_mode = mock_hub_config.single_node_mode
    spawner.quota_enabled = mock_hub_config.quota_enabled
    spawner.resource_images = mock_hub_config.resource_images
    spawner.resource_requirements = mock_hub_config.resource_requirements
    spawner.accelerator_options = mock_hub_config.accelerator_options
    spawner.team_resource_mapping = mock_hub_config.team_resource_mapping
    spawner.node_selector_mapping = mock_hub_config.node_selector_mapping
    spawner.environment_mapping = mock_hub_config.environment_mapping
    spawner.quota_rates = mock_hub_config.quota_rates
    spawner.default_quota = mock_hub_config.default_quota
    spawner.minimum_quota_to_start = mock_hub_config.minimum_quota_to_start

    # Add actual methods from the class
    from core.spawner.kubernetes import RemoteLabKubeSpawner
    spawner._parse_memory_string = RemoteLabKubeSpawner._parse_memory_string.__get__(spawner)
    spawner.get_quota_rate = RemoteLabKubeSpawner.get_quota_rate.__get__(spawner)

    return spawner


@pytest.fixture
def mock_user():
    """Create a mock JupyterHub user."""
    user = Mock()
    user.name = "test-user"
    user.id = "123"
    user.auth_state = {
        "access_token": "test-token-123",
        "github_user": {"login": "testuser"},
    }
    return user


@pytest.fixture
def mock_quota_manager():
    """Create a mock QuotaManager."""
    manager = Mock()
    manager.can_start_container = Mock(return_value=(True, "OK", 30))
    manager.start_usage_session = Mock(return_value="session-uuid-123")
    manager.end_usage_session = Mock(return_value=(20, 33.3))
    manager.is_unlimited_in_db = Mock(return_value=False)
    return manager
