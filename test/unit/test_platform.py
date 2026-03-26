"""Unit tests for platform detection."""

from cli.lib.platform import (
    PLATFORM,
    check_docker,
    get_user_info,
)


class TestPlatform:
    def test_platform_is_known(self):
        assert PLATFORM in ("linux", "darwin", "windows")

    def test_get_user_info(self):
        info = get_user_info()
        assert "user" in info
        assert "hostname" in info
        assert "platform" in info
        assert info["platform"] == PLATFORM

    def test_check_docker_returns_string_or_none(self):
        result = check_docker()
        assert result is None or isinstance(result, str)
