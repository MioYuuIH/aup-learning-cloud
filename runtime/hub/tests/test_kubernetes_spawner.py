"""
Unit tests for RemoteLabKubeSpawner
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.spawner.kubernetes import RemoteLabKubeSpawner


class TestParseMemoryString:
    """Tests for _parse_memory_string method"""

    def test_parse_int_input(self, mock_spawner):
        """Test parsing integer input (already in GB)"""
        result = mock_spawner._parse_memory_string(4)
        assert result == 4.0

    def test_parse_float_input(self, mock_spawner):
        """Test parsing float input"""
        result = mock_spawner._parse_memory_string(4.5)
        assert result == 4.5

    def test_parse_gi_format(self, mock_spawner):
        """Test parsing Kubernetes Gi format (Gigabytes binary)"""
        result = mock_spawner._parse_memory_string("4Gi")
        assert result == 4.0

    def test_parse_mi_format(self, mock_spawner):
        """Test parsing Mi format (Mebibytes)"""
        result = mock_spawner._parse_memory_string("1024Mi")
        assert abs(result - 1.0) < 0.01  # Should be ~1GB

    def test_parse_g_format(self, mock_spawner):
        """Test parsing G format (Gigabytes decimal)"""
        result = mock_spawner._parse_memory_string("4G")
        assert result == 4.0

    def test_parse_m_format(self, mock_spawner):
        """Test parsing M format (Megabytes decimal)"""
        result = mock_spawner._parse_memory_string("1000M")
        assert result == 1.0

    def test_parse_ti_format(self, mock_spawner):
        """Test parsing Ti format (Tebibytes)"""
        result = mock_spawner._parse_memory_string("1Ti")
        assert result == 1024.0

    def test_parse_t_format(self, mock_spawner):
        """Test parsing T format (Terabytes decimal)"""
        result = mock_spawner._parse_memory_string("1T")
        assert result == 1000.0

    def test_parse_digit_string(self, mock_spawner):
        """Test parsing digit-only string"""
        result = mock_spawner._parse_memory_string("8")
        assert result == 8.0

    def test_parse_invalid_format(self, mock_spawner):
        """Test parsing invalid format returns default 1.0"""
        result = mock_spawner._parse_memory_string("invalid-format")
        assert result == 1.0

    def test_parse_string_with_spaces(self, mock_spawner):
        """Test parsing string with leading/trailing spaces"""
        result = mock_spawner._parse_memory_string("  4Gi  ")
        assert result == 4.0


class TestGetQuotaRate:
    """Tests for get_quota_rate method"""

    def test_quota_rate_cpu(self, mock_spawner):
        """Test getting quota rate for CPU"""
        rate = mock_spawner.get_quota_rate("cpu")
        assert rate == 10

    def test_quota_rate_gpu(self, mock_spawner):
        """Test getting quota rate for GPU"""
        rate = mock_spawner.get_quota_rate("gpu")
        assert rate == 100

    def test_quota_rate_npu(self, mock_spawner):
        """Test getting quota rate for NPU"""
        rate = mock_spawner.get_quota_rate("npu")
        assert rate == 150

    def test_quota_rate_unknown_type(self, mock_spawner):
        """Test getting quota rate for unknown accelerator defaults to CPU"""
        rate = mock_spawner.get_quota_rate("unknown-accelerator")
        assert rate == 10  # Falls back to CPU rate

    def test_quota_rate_none_accelerator(self, mock_spawner):
        """Test getting quota rate when accelerator is None"""
        rate = mock_spawner.get_quota_rate(None)
        assert rate == 10  # Returns CPU rate

    def test_quota_rate_empty_string(self, mock_spawner):
        """Test getting quota rate with empty string"""
        rate = mock_spawner.get_quota_rate("")
        assert rate == 10  # Returns CPU rate


class TestOptionsFromForm:
    """Tests for options_from_form method"""

    def test_valid_resource_selection(self):
        """Test parsing valid resource selection"""
        # We need a real instance for this test
        from core.spawner.kubernetes import RemoteLabKubeSpawner
        spawner = RemoteLabKubeSpawner()
        spawner.resource_images = {
            "pytorch": "amd-pytorch:latest",
            "tensorflow": "amd-tensorflow:latest",
        }
        spawner.log = Mock()

        formdata = {
            "runtime": ["20"],
            "resource_type": ["pytorch"],
            "gpu_selection_pytorch": [None],
        }

        options = spawner.options_from_form(formdata)

        assert options["runtime_minutes"] == 20
        assert options["resource_type"] == "pytorch"
        assert options["gpu_selection"] is None

    def test_invalid_resource_type(self):
        """Test that unknown resource type raises error"""
        from core.spawner.kubernetes import RemoteLabKubeSpawner
        spawner = RemoteLabKubeSpawner()
        spawner.resource_images = {"pytorch": "amd-pytorch:latest"}

        formdata = {
            "runtime": ["20"],
            "resource_type": ["unknown-resource"],
            "gpu_selection_unknown-resource": [None],
        }

        with pytest.raises(RuntimeError, match="Unknown Resource"):
            spawner.options_from_form(formdata)

    def test_multiple_resource_types_error(self):
        """Test that selecting multiple resources raises error"""
        from core.spawner.kubernetes import RemoteLabKubeSpawner
        spawner = RemoteLabKubeSpawner()
        spawner.resource_images = {
            "pytorch": "amd-pytorch:latest",
            "tensorflow": "amd-tensorflow:latest",
        }

        formdata = {
            "runtime": ["20"],
            "resource_type": ["pytorch", "tensorflow"],
            "gpu_selection_pytorch": [None],
        }

        with pytest.raises(RuntimeError, match="Selected 0 or more than 1 resources"):
            spawner.options_from_form(formdata)

    def test_custom_runtime(self):
        """Test parsing custom runtime value"""
        from core.spawner.kubernetes import RemoteLabKubeSpawner
        spawner = RemoteLabKubeSpawner()
        spawner.resource_images = {"pytorch": "amd-pytorch:latest"}
        spawner.log = Mock()

        formdata = {
            "runtime": ["60"],
            "resource_type": ["pytorch"],
            "gpu_selection_pytorch": [None],
        }

        options = spawner.options_from_form(formdata)
        assert options["runtime_minutes"] == 60


class TestResourceConfiguration:
    """Tests for resource and configuration validation"""

    def test_resource_images_configured(self, mock_spawner):
        """Test that resource images are properly configured"""
        assert "pytorch" in mock_spawner.resource_images
        assert "tensorflow" in mock_spawner.resource_images
        assert mock_spawner.resource_images["pytorch"] == "amd-pytorch:latest"

    def test_resource_requirements_configured(self, mock_spawner):
        """Test that resource requirements are properly configured"""
        assert "pytorch" in mock_spawner.resource_requirements
        pytorch_reqs = mock_spawner.resource_requirements["pytorch"]
        assert pytorch_reqs["cpu"] == "2"
        assert pytorch_reqs["memory"] == "4Gi"

    def test_team_resource_mapping_exists(self, mock_spawner):
        """Test that team resource mapping is configured"""
        assert "official" in mock_spawner.team_resource_mapping
        assert "pytorch" in mock_spawner.team_resource_mapping["official"]

    def test_quota_rates_configured(self, mock_spawner):
        """Test that quota rates are properly configured"""
        assert mock_spawner.quota_rates["cpu"] == 10
        assert mock_spawner.quota_rates["gpu"] == 100
        assert mock_spawner.quota_rates["npu"] == 150


class TestConfigureFromConfig:
    """Tests for configure_from_config class method"""

    def test_configure_from_config(self, mock_hub_config):
        """Test that configure_from_config sets class attributes"""
        RemoteLabKubeSpawner.configure_from_config(mock_hub_config)

        # Verify class attributes were set
        assert RemoteLabKubeSpawner.resource_images == mock_hub_config.resource_images
        assert RemoteLabKubeSpawner.resource_requirements == mock_hub_config.resource_requirements
        assert RemoteLabKubeSpawner.github_org_name == mock_hub_config.github_org_name
        assert RemoteLabKubeSpawner.quota_rates == mock_hub_config.quota_rates


class TestMemoryCalculations:
    """Integration tests for memory parsing and configuration"""

    def test_memory_conversion_examples(self, mock_spawner):
        """Test common memory conversion scenarios"""
        test_cases = [
            ("2Gi", 2.0),
            ("4Gi", 4.0),
            ("8Gi", 8.0),
            ("512Mi", 0.5),
            ("1024Mi", 1.0),
            ("2048Mi", 2.0),
        ]

        for input_val, expected in test_cases:
            result = mock_spawner._parse_memory_string(input_val)
            assert abs(result - expected) < 0.01, f"Failed for {input_val}"

    def test_quota_rate_calculation(self, mock_spawner):
        """Test quota rate for different resources"""
        # For 1 hour GPU usage
        cpu_rate = mock_spawner.get_quota_rate("cpu")
        gpu_rate = mock_spawner.get_quota_rate("gpu")
        npu_rate = mock_spawner.get_quota_rate("npu")

        # Verify hierarchy: GPU > NPU > CPU (typical config)
        assert cpu_rate < gpu_rate
        assert gpu_rate < npu_rate
