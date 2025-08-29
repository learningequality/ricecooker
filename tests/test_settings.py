import os
import sys

import pytest
from mock import patch
from requests import PreparedRequest

from ricecooker import chefs
from ricecooker.utils.request_utils import DomainSpecificAuth


settings = {"thumbnails": True, "compress": True}


def test_settings_unset_default():
    chef = chefs.SushiChef()

    for setting in settings:
        assert chef.get_setting(setting) is None
        assert chef.get_setting(setting, default=False) is False


def test_settings():
    chef = chefs.SushiChef()

    for setting in settings:
        value = settings[setting]
        chef.SETTINGS[setting] = value
        assert chef.get_setting(setting) == value
        assert chef.get_setting(setting, default=None) == value


def test_cli_args_override_settings():
    """
    For settings that can be controlled via the command line, ensure that the command line setting
    takes precedence over the default setting.
    """

    test_argv = ["sushichef.py", "--compress", "--thumbnails", "--token", "12345"]

    with patch.object(sys, "argv", test_argv):
        chef = chefs.SushiChef()
        chef.SETTINGS["thumbnails"] = False
        chef.SETTINGS["compress"] = False

        assert chef.get_setting("thumbnails") is False
        assert chef.get_setting("compress") is False

        chef.parse_args_and_options()
        assert chef.get_setting("thumbnails") is True
        assert chef.get_setting("compress") is True

    test_argv = ["sushichef.py", "--compress", "--thumbnails", "--token", "12345"]

    with patch.object(sys, "argv", test_argv):
        chef = chefs.SushiChef()

        assert len(chef.SETTINGS) == 0

        assert chef.get_setting("thumbnails") is None
        assert chef.get_setting("compress") is None

        chef.parse_args_and_options()
        assert chef.get_setting("thumbnails") is True
        assert chef.get_setting("compress") is True

    # now test without setting the flags
    test_argv = ["sushichef.py", "--token", "12345"]

    with patch.object(sys, "argv", test_argv):
        chef = chefs.SushiChef()
        chef.SETTINGS["thumbnails"] = False
        chef.SETTINGS["compress"] = False

        assert chef.get_setting("thumbnails") is False
        assert chef.get_setting("compress") is False

        chef.parse_args_and_options()
        assert chef.get_setting("thumbnails") is False
        assert chef.get_setting("compress") is False


# Domain-specific authentication tests
def test_domain_auth_with_valid_environment_variables():
    """Test DomainSpecificAuth initialization and header application with valid environment variables."""
    domain_to_headers = {
        "example.com": {
            "Authorization": "EXAMPLE_AUTH_TOKEN",
            "X-API-Key": "EXAMPLE_API_KEY",
        }
    }

    with patch.dict(
        os.environ,
        {"EXAMPLE_AUTH_TOKEN": "Bearer token123", "EXAMPLE_API_KEY": "key456"},
    ):
        auth = DomainSpecificAuth(domain_to_headers)

        # Create a mock request
        request = PreparedRequest()
        request.prepare(method="GET", url="https://example.com/data")
        request.headers = {"Content-Type": "application/json"}

        # Apply authentication
        result = auth(request)

        # Verify headers were added
        assert result.headers["Authorization"] == "Bearer token123"
        assert result.headers["X-API-Key"] == "key456"
        assert (
            result.headers["Content-Type"] == "application/json"
        )  # existing header preserved


def test_domain_auth_with_missing_environment_variable():
    """Test DomainSpecificAuth fails when environment variable is missing."""
    domain_to_headers = {"example.com": {"Authorization": "MISSING_TOKEN"}}

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(
            ValueError,
            match="Environment variable for header value 'MISSING_TOKEN' not set.",
        ):
            DomainSpecificAuth(domain_to_headers)


def test_domain_auth_no_headers_for_non_matching_domain():
    """Test that headers are not added for non-matching domains."""
    domain_to_headers = {"api.example.com": {"Authorization": "EXAMPLE_TOKEN"}}

    with patch.dict(os.environ, {"EXAMPLE_TOKEN": "Bearer secret123"}):
        auth = DomainSpecificAuth(domain_to_headers)

        # Create a mock request for different domain
        request = PreparedRequest()
        request.prepare(method="GET", url="https://different.com/data")
        request.headers = {"Content-Type": "application/json"}

        # Apply authentication
        result = auth(request)

        # Verify no auth headers were added
        assert "Authorization" not in result.headers
        assert (
            result.headers["Content-Type"] == "application/json"
        )  # existing header preserved
