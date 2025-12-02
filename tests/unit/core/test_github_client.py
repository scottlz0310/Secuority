"""Unit tests for GitHubClient."""

import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from secuority.core.github_client import GitHubClient
from secuority.models.exceptions import GitHubAPIError


def create_mock_response(content: bytes) -> MagicMock:
    """Create a mock response object that works as a context manager."""
    mock_response = MagicMock()
    mock_response.read.return_value = content
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


class TestGitHubClient:
    """Test GitHubClient functionality."""

    @pytest.fixture
    def client(self) -> GitHubClient:
        """Create GitHubClient instance with test token."""
        return GitHubClient(token="test_token")

    @pytest.fixture
    def client_no_token(self) -> GitHubClient:
        """Create GitHubClient instance without token."""
        return GitHubClient(token=None)

    def test_init_with_token(self) -> None:
        """Test initializing client with token."""
        client = GitHubClient(token="test_token")

        assert client.token == "test_token"
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == "token test_token"

    def test_init_without_token(self) -> None:
        """Test initializing client without token."""
        with patch.dict("os.environ", {}, clear=True):
            client = GitHubClient()

        assert client.token is None
        assert "Authorization" not in client.headers

    def test_init_with_env_token(self) -> None:
        """Test initializing client with environment variable token."""
        with patch.dict("os.environ", {"GITHUB_PERSONAL_ACCESS_TOKEN": "env_token"}):
            client = GitHubClient()

        assert client.token == "env_token"

    def test_make_request_success(self, client: GitHubClient) -> None:
        """Test successful API request."""
        mock_response = create_mock_response(b'{"key": "value"}')

        with patch("secuority.core.github_client.urlopen", return_value=mock_response):
            result = client._make_request("/test")

        assert result == {"key": "value"}

    def test_make_request_401_error(self, client: GitHubClient) -> None:
        """Test API request with 401 authentication error."""
        mock_error = HTTPError("url", 401, "Unauthorized", {}, None)

        with patch("secuority.core.github_client.urlopen", side_effect=mock_error):
            with pytest.raises(GitHubAPIError, match="authentication failed"):
                client._make_request("/test")

    def test_make_request_403_error(self, client: GitHubClient) -> None:
        """Test API request with 403 rate limit error."""
        mock_error = HTTPError("url", 403, "Forbidden", {}, None)

        with patch("secuority.core.github_client.urlopen", side_effect=mock_error):
            with pytest.raises(GitHubAPIError, match="rate limit"):
                client._make_request("/test")

    def test_make_request_404_error(self, client: GitHubClient) -> None:
        """Test API request with 404 not found error."""
        mock_error = HTTPError("url", 404, "Not Found", {}, None)

        with patch("secuority.core.github_client.urlopen", side_effect=mock_error):
            with pytest.raises(GitHubAPIError, match="not found"):
                client._make_request("/test")

    def test_make_request_network_error(self, client: GitHubClient) -> None:
        """Test API request with network error."""
        mock_error = URLError("Network error")

        with patch("secuority.core.github_client.urlopen", side_effect=mock_error):
            with pytest.raises(GitHubAPIError, match="Network error"):
                client._make_request("/test")

    def test_make_request_invalid_json(self, client: GitHubClient) -> None:
        """Test API request with invalid JSON response."""
        mock_response = create_mock_response(b"invalid json")

        with patch("secuority.core.github_client.urlopen", return_value=mock_response):
            with pytest.raises(GitHubAPIError, match="Invalid JSON"):
                client._make_request("/test")

    def test_check_push_protection_enabled(self, client: GitHubClient) -> None:
        """Test checking push protection when enabled."""
        call_count = [0]

        def mock_urlopen(request):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: repo data
                return create_mock_response(b'{"security_and_analysis": {}}')
            # Second call: push protection endpoint
            return create_mock_response(b'{"enabled": true}')

        with patch("secuority.core.github_client.urlopen", side_effect=mock_urlopen):
            result = client.check_push_protection("owner", "repo")

        assert result is True

    def test_check_push_protection_disabled(self, client: GitHubClient) -> None:
        """Test checking push protection when disabled."""
        call_count = [0]

        def mock_urlopen(request):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: repo data
                return create_mock_response(b'{"security_and_analysis": {}}')
            # Second call: push protection endpoint
            return create_mock_response(b'{"enabled": false}')

        with patch("secuority.core.github_client.urlopen", side_effect=mock_urlopen):
            result = client.check_push_protection("owner", "repo")

        assert result is False

    def test_check_push_protection_fallback(self, client: GitHubClient) -> None:
        """Test push protection check with fallback to general settings."""
        call_count = [0]

        def mock_urlopen(request):
            call_count[0] += 1

            if call_count[0] == 1:
                # First call: repo data
                return create_mock_response(b'{"security_and_analysis": {"secret_scanning": {"status": "enabled"}}}')
            # Second call: push protection endpoint fails
            raise HTTPError("url", 404, "Not Found", {}, None)

        with patch("secuority.core.github_client.urlopen", side_effect=mock_urlopen):
            result = client.check_push_protection("owner", "repo")

        assert result is True

    def test_get_dependabot_config_enabled(self, client: GitHubClient) -> None:
        """Test getting Dependabot config when enabled."""
        call_count = [0]

        def mock_urlopen(request):
            call_count[0] += 1

            if call_count[0] == 1:
                # Vulnerability alerts endpoint
                return create_mock_response(b"{}")
            # Config file endpoint
            return create_mock_response(b'{"content": "base64content"}')

        with patch("secuority.core.github_client.urlopen", side_effect=mock_urlopen):
            result = client.get_dependabot_config("owner", "repo")

        assert result["enabled"] is True
        assert result["config_file_exists"] is True

    def test_get_dependabot_config_disabled(self, client: GitHubClient) -> None:
        """Test getting Dependabot config when disabled."""

        def mock_urlopen(request):
            # Both endpoints fail
            raise HTTPError("url", 404, "Not Found", {}, None)

        with patch("secuority.core.github_client.urlopen", side_effect=mock_urlopen):
            result = client.get_dependabot_config("owner", "repo")

        assert result["enabled"] is False
        assert result["config_file_exists"] is False

    def test_list_workflows_success(self, client: GitHubClient) -> None:
        """Test listing workflows successfully."""
        mock_response = create_mock_response(b'{"workflows": [{"name": "CI", "path": ".github/workflows/ci.yml"}]}')

        with patch("secuority.core.github_client.urlopen", return_value=mock_response):
            result = client.list_workflows("owner", "repo")

        assert len(result) == 1
        assert result[0]["name"] == "CI"

    def test_list_workflows_empty(self, client: GitHubClient) -> None:
        """Test listing workflows when none exist."""
        mock_response = create_mock_response(b'{"workflows": []}')

        with patch("secuority.core.github_client.urlopen", return_value=mock_response):
            result = client.list_workflows("owner", "repo")

        assert len(result) == 0

    def test_check_security_settings_success(self, client: GitHubClient) -> None:
        """Test checking security settings successfully."""
        call_count = [0]

        def mock_urlopen(request):
            call_count[0] += 1

            if call_count[0] == 1:
                # Repo data
                return create_mock_response(
                    json.dumps(
                        {
                            "private": False,
                            "has_vulnerability_alerts": True,
                            "security_and_analysis": {
                                "secret_scanning": {"status": "enabled"},
                                "secret_scanning_push_protection": {"status": "enabled"},
                                "private_vulnerability_reporting": {"status": "enabled"},
                            },
                        },
                    ).encode(),
                )
            # SECURITY.md check
            return create_mock_response(b'{"name": "SECURITY.md"}')

        with patch("secuority.core.github_client.urlopen", side_effect=mock_urlopen):
            result = client.check_security_settings("owner", "repo")

        assert result["secret_scanning"] is True
        assert result["secret_scanning_push_protection"] is True
        assert result["security_policy"] is True

    def test_check_security_settings_no_security_md(self, client: GitHubClient) -> None:
        """Test checking security settings when SECURITY.md doesn't exist."""
        call_count = [0]

        def mock_urlopen(request):
            call_count[0] += 1

            if call_count[0] == 1:
                # Repo data
                return create_mock_response(b'{"private": true, "security_and_analysis": {}}')
            # SECURITY.md doesn't exist
            raise HTTPError("url", 404, "Not Found", {}, None)

        with patch("secuority.core.github_client.urlopen", side_effect=mock_urlopen):
            result = client.check_security_settings("owner", "repo")

        assert result["security_policy"] is False
        assert result["is_private"] is True

    def test_is_authenticated_true(self, client: GitHubClient) -> None:
        """Test authentication check when authenticated."""
        mock_response = create_mock_response(b'{"login": "testuser"}')

        with patch("secuority.core.github_client.urlopen", return_value=mock_response):
            result = client.is_authenticated()

        assert result is True

    def test_is_authenticated_false_no_token(self) -> None:
        """Test authentication check when no token."""
        with patch.dict("os.environ", {}, clear=True):
            client = GitHubClient(token=None)
            result = client.is_authenticated()

        assert result is False

    def test_is_authenticated_false_invalid_token(self, client: GitHubClient) -> None:
        """Test authentication check with invalid token."""
        mock_error = HTTPError("url", 401, "Unauthorized", {}, None)

        with patch("secuority.core.github_client.urlopen", side_effect=mock_error):
            result = client.is_authenticated()

        assert result is False

    def test_safe_api_call_success(self, client: GitHubClient) -> None:
        """Test safe API call with successful response."""
        mock_response = create_mock_response(b'{"data": "value"}')

        with patch("secuority.core.github_client.urlopen", return_value=mock_response):
            result = client.safe_api_call("test operation", "/test")

        assert result == {"data": "value"}

    def test_safe_api_call_with_fallback(self, client: GitHubClient) -> None:
        """Test safe API call with error and fallback value."""
        mock_error = HTTPError("url", 404, "Not Found", {}, None)

        with patch("secuority.core.github_client.urlopen", side_effect=mock_error):
            result = client.safe_api_call("test operation", "/test", fallback_value={"default": "value"})

        assert result == {"default": "value"}

    def test_safe_api_call_no_logging(self, client: GitHubClient) -> None:
        """Test safe API call without error logging."""
        mock_error = HTTPError("url", 404, "Not Found", {}, None)

        with patch("secuority.core.github_client.urlopen", side_effect=mock_error):
            with patch("secuority.core.github_client.logger") as mock_logger:
                result = client.safe_api_call("test operation", "/test", fallback_value=None, log_errors=False)

        assert result is None
        mock_logger.warning.assert_not_called()

    def test_get_api_status_authenticated(self, client: GitHubClient) -> None:
        """Test getting API status when authenticated."""
        call_count = [0]

        def mock_urlopen(request):
            call_count[0] += 1

            if call_count[0] == 1:
                # User endpoint
                return create_mock_response(b'{"login": "testuser"}')
            # Rate limit endpoint
            return create_mock_response(b'{"rate": {"limit": 5000, "remaining": 4999}}')

        with patch("secuority.core.github_client.urlopen", side_effect=mock_urlopen):
            status = client.get_api_status()

        assert status["has_token"] is True
        assert status["authenticated"] is True
        assert status["api_accessible"] is True
        assert status["user"] == "testuser"
        assert status["rate_limit_info"] is not None

    def test_get_api_status_no_token(self) -> None:
        """Test getting API status without token."""
        with patch.dict("os.environ", {}, clear=True):
            client = GitHubClient(token=None)
            status = client.get_api_status()

        assert status["has_token"] is False
        assert status["authenticated"] is False
        assert len(status["errors"]) > 0

    def test_get_api_status_auth_failed(self, client: GitHubClient) -> None:
        """Test getting API status when authentication fails."""
        call_count = [0]

        def mock_urlopen(request):
            call_count[0] += 1

            if call_count[0] == 1:
                # User endpoint fails
                raise HTTPError("url", 401, "Unauthorized", {}, None)
            # Zen endpoint succeeds (API accessible)
            return create_mock_response(b'"Keep it simple"')

        with patch("secuority.core.github_client.urlopen", side_effect=mock_urlopen):
            status = client.get_api_status()

        assert status["has_token"] is True
        assert status["authenticated"] is False
        assert status["api_accessible"] is True
        assert len(status["errors"]) > 0
