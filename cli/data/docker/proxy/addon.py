"""Mitmproxy addon for sandbox logging, content inspection, and DLP.

Writes request/response metadata to the audit volume as unified event
envelope JSONL. Optionally applies content inspection rules and DLP
provider webhooks.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from mitmproxy import http

LOG_DIR = Path("/var/log/sandbox/proxy")
PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "default")
LOG_SINKS = os.environ.get("SANDBOX_LOG_SINKS", "file")
DLP_PROVIDER = os.environ.get("SANDBOX_DLP_PROVIDER", "none")
DLP_WEBHOOK_URL = os.environ.get("SANDBOX_DLP_WEBHOOK_URL", "")

INSPECTION_RULES = []
INSPECTION_FILE = Path("/etc/proxy/inspection.yaml")

if INSPECTION_FILE.exists():
    try:
        data = yaml.safe_load(INSPECTION_FILE.read_text())
        INSPECTION_RULES = data.get("rules", []) if data else []
    except yaml.YAMLError:
        pass


def _emit_event(event_type: str, payload: dict) -> None:
    """Write a unified event envelope."""
    envelope = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "project": PROJECT,
        "session_id": "",
        "source": "proxy",
        "payload": payload,
    }

    line = json.dumps(envelope) + "\n"

    if "file" in LOG_SINKS:
        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = LOG_DIR / today
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "requests.jsonl"
        with open(log_file, "a") as f:
            f.write(line)

    if "stdout" in LOG_SINKS:
        print(line, end="", flush=True)


def _check_inspection_rules(content: str) -> list[dict]:
    """Check content against inspection rules. Returns list of violations."""
    violations = []
    for rule in INSPECTION_RULES:
        pattern = rule.get("pattern", "")
        action = rule.get("action", "alert")
        name = rule.get("name", pattern)

        if pattern and re.search(pattern, content):
            violations.append({
                "rule": name,
                "action": action,
                "pattern": pattern,
            })
    return violations


def _call_dlp_webhook(flow: http.HTTPFlow, direction: str, content: str) -> dict | None:
    """Call DLP webhook if configured. Returns response or None."""
    if DLP_PROVIDER != "webhook" or not DLP_WEBHOOK_URL:
        return None

    import urllib.request

    try:
        payload = json.dumps({
            "url": flow.request.pretty_url,
            "method": flow.request.method,
            "direction": direction,
            "content_length": len(content),
            "content_preview": content[:1000],
        }).encode()

        req = urllib.request.Request(
            DLP_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read())
    except Exception:
        return None


class SandboxAddon:
    def request(self, flow: http.HTTPFlow) -> None:
        body = flow.request.get_text() or ""

        payload = {
            "method": flow.request.method,
            "url": flow.request.pretty_url,
            "host": flow.request.host,
            "content_length": len(body),
        }

        if body and INSPECTION_RULES:
            violations = _check_inspection_rules(body)
            if violations:
                payload["violations"] = violations
                for v in violations:
                    if v["action"] == "block":
                        flow.response = http.Response.make(
                            403,
                            json.dumps({"error": "Blocked by content inspection", "rule": v["rule"]}),
                            {"Content-Type": "application/json"},
                        )
                        payload["blocked"] = True
                        _emit_event("proxy_request", payload)
                        return

        if body and DLP_PROVIDER != "none":
            dlp_result = _call_dlp_webhook(flow, "request", body)
            if dlp_result:
                payload["dlp"] = dlp_result
                action = dlp_result.get("action", "log")
                if action == "block":
                    flow.response = http.Response.make(
                        403,
                        json.dumps({"error": "Blocked by DLP policy"}),
                        {"Content-Type": "application/json"},
                    )
                    payload["blocked"] = True
                    _emit_event("proxy_request", payload)
                    return

        _emit_event("proxy_request", payload)

    def response(self, flow: http.HTTPFlow) -> None:
        body = flow.response.get_text() or ""

        payload = {
            "method": flow.request.method,
            "url": flow.request.pretty_url,
            "status_code": flow.response.status_code,
            "content_length": len(body),
        }

        if body and INSPECTION_RULES:
            violations = _check_inspection_rules(body)
            if violations:
                payload["violations"] = violations

        _emit_event("proxy_request", payload)


addons = [SandboxAddon()]
