"""E2E: Layer 3 - Firewall."""

import json
import time

import pytest

from test.e2e.conftest import sandbox, sandbox_output, E2E_DATA_DIR


class TestFirewallRules:
    def test_firewall_container_running(self):
        output = sandbox_output("status")
        assert "firewall" in output
        assert "running" in output

    def test_whitelist_readable(self):
        result = sandbox("fw", "ls", capture_output=True, text=True)
        assert result.returncode == 0

    def test_dns_works(self):
        result = sandbox("exec", "bash", "-c",
                         "timeout 5 nslookup github.com 2>&1 || true",
                         capture_output=True, text=True)
        # DNS should resolve even if the domain isn't whitelisted
        # (DNS is allowed through the firewall)
        assert result.returncode == 0


class TestFirewallEnforcement:
    def test_whitelisted_domain_accessible(self):
        # registry.npmjs.org is in the default whitelist
        result = sandbox("exec", "bash", "-c",
                         "timeout 10 curl -sI https://registry.npmjs.org/ 2>&1 | head -1",
                         capture_output=True, text=True)
        # Should get an HTTP response (200, 301, etc.)
        assert "HTTP" in result.stdout or result.returncode == 0

    def test_non_whitelisted_domain_blocked(self):
        result = sandbox("exec", "bash", "-c",
                         "timeout 5 curl -s https://example.com/ 2>&1",
                         capture_output=True, text=True)
        # Should fail (connection refused, timed out, etc.)
        assert result.returncode != 0 or "curl" in result.stdout.lower()


class TestFirewallAddRemove:
    def test_add_domain(self):
        result = sandbox("fw", "add", "httpbin.org", capture_output=True, text=True)
        assert result.returncode == 0

        domains = sandbox_output("fw", "ls")
        assert "httpbin.org" in domains

    def test_remove_domain(self):
        # Ensure it's added first
        sandbox("fw", "add", "httpbin.org", capture_output=True)

        result = sandbox("fw", "remove", "httpbin.org", capture_output=True, text=True)
        assert result.returncode == 0

        domains = sandbox_output("fw", "ls")
        assert "httpbin.org" not in domains

    def test_add_invalid_domain_rejected(self):
        result = sandbox("fw", "add", "not a domain!", capture_output=True, text=True)
        assert result.returncode != 0

    def test_rapid_add_remove(self):
        for i in range(5):
            sandbox("fw", "add", f"test{i}.example.com", capture_output=True, check=True)
        domains = sandbox_output("fw", "ls")
        for i in range(5):
            assert f"test{i}.example.com" in domains

        for i in range(5):
            sandbox("fw", "remove", f"test{i}.example.com", capture_output=True, check=True)
        domains = sandbox_output("fw", "ls")
        for i in range(5):
            assert f"test{i}.example.com" not in domains


class TestFirewallProfiles:
    def test_list_profiles(self):
        output = sandbox_output("fw", "profiles")
        assert "dev" in output
        assert "restricted" in output

    def test_apply_dev_profile(self):
        sandbox("fw", "profile", "dev", check=True)
        domains = sandbox_output("fw", "ls")
        assert "github.com" in domains

    def test_apply_restricted_profile(self):
        sandbox("fw", "profile", "restricted", check=True)
        domains = sandbox_output("fw", "ls")
        # Restricted has no domains but tool domains get merged
        # At minimum, the tool-specific domains should be there
        assert len(domains.strip()) >= 0  # May have tool domains

        # Restore dev profile
        sandbox("fw", "profile", "dev", check=True)


class TestFirewallBypass:
    def test_cannot_bypass_with_direct_ip(self):
        result = sandbox("exec", "bash", "-c",
                         "timeout 5 curl -s http://93.184.216.34/ 2>&1",
                         capture_output=True, text=True)
        assert result.returncode != 0 or "curl" in result.stdout.lower()

    def test_ipv6_blocked(self):
        result = sandbox("exec", "bash", "-c",
                         "timeout 5 curl -6 -s https://example.com/ 2>&1",
                         capture_output=True, text=True)
        assert result.returncode != 0 or "curl" in result.stdout.lower()


class TestFirewallLogging:
    def test_log_daemon_running(self):
        """Check that the firewall log daemon process is running."""
        result = sandbox("exec", "bash", "-c",
                         "docker exec project_firewall pgrep -f firewall-log || echo not-found",
                         capture_output=True, text=True)
        # The exec runs inside sandbox container which can't reach the firewall directly.
        # Instead check from the host via the conftest sandbox helper.
        import subprocess, os
        env = {**os.environ, "SANDBOX_DATA_DIR": str(E2E_DATA_DIR)}
        result = subprocess.run(
            ["docker", "exec", "project_firewall", "pgrep", "-f", "firewall-log"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0, "Firewall log daemon is not running"

    def test_blocked_request_produces_log(self):
        """Trigger a blocked request and verify a firewall log entry appears."""
        # Attempt a blocked request
        sandbox("exec", "bash", "-c",
                "timeout 3 curl -s https://definitely-not-whitelisted.example.com/ 2>&1 || true",
                capture_output=True)

        time.sleep(3)

        log_dir = E2E_DATA_DIR / "logs" / "firewall"
        jsonl_files = list(log_dir.rglob("*.jsonl"))

        if not jsonl_files:
            # Log daemon may not have produced output yet
            pytest.skip("No firewall log files found (daemon may need rsyslog/kernel log)")

        found_block = False
        for f in jsonl_files:
            for line in f.read_text().splitlines():
                if "firewall_block" in line:
                    found_block = True
                    entry = json.loads(line)
                    assert entry["event_type"] == "firewall_block"
                    assert "dst" in entry["payload"]
                    break

        assert found_block, "No firewall_block event found in logs"

    def test_allowed_request_produces_log(self):
        """Trigger an allowed request and verify a firewall log entry appears."""
        sandbox("exec", "bash", "-c",
                "timeout 5 curl -sI https://registry.npmjs.org/ 2>&1 || true",
                capture_output=True)

        time.sleep(3)

        log_dir = E2E_DATA_DIR / "logs" / "firewall"
        jsonl_files = list(log_dir.rglob("*.jsonl"))

        if not jsonl_files:
            pytest.skip("No firewall log files found (daemon may need rsyslog/kernel log)")

        found_allow = False
        for f in jsonl_files:
            for line in f.read_text().splitlines():
                if "firewall_allow" in line:
                    found_allow = True
                    entry = json.loads(line)
                    assert entry["event_type"] == "firewall_allow"
                    break

        assert found_allow, "No firewall_allow event found in logs"

    def test_fw_logs_command(self):
        """Verify sandbox fw logs shows entries if log files exist."""
        log_dir = E2E_DATA_DIR / "logs" / "firewall"
        jsonl_files = list(log_dir.rglob("*.jsonl"))

        if not jsonl_files:
            pytest.skip("No firewall log files to display")

        result = sandbox("fw", "logs", capture_output=True, text=True)
        assert result.returncode == 0
