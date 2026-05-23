"""
Live API endpoint verification script.

Usage:
    uv run python scripts/check_endpoints.py
    uv run python scripts/check_endpoints.py --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

API_PREFIX = "/api/v1"
EXPECTED_ROUTES = [
    ("GET", "/health"),
    ("POST", f"{API_PREFIX}/auth/register"),
    ("POST", f"{API_PREFIX}/auth/login"),
    ("POST", f"{API_PREFIX}/auth/refresh"),
    ("GET", f"{API_PREFIX}/auth/me"),
    ("GET", f"{API_PREFIX}/users/me"),
    ("PATCH", f"{API_PREFIX}/users/me"),
    ("GET", f"{API_PREFIX}/hackathons"),
    ("GET", f"{API_PREFIX}/hackathons/search"),
    ("GET", f"{API_PREFIX}/hackathons/trending"),
    ("GET", f"{API_PREFIX}/hackathons/{{id}}"),
    ("GET", f"{API_PREFIX}/bookmarks"),
    ("POST", f"{API_PREFIX}/bookmarks/{{id}}"),
    ("DELETE", f"{API_PREFIX}/bookmarks/{{id}}"),
    ("GET", f"{API_PREFIX}/themes"),
    ("GET", f"{API_PREFIX}/platforms"),
    ("GET", f"{API_PREFIX}/trends/hackathons"),
    ("GET", f"{API_PREFIX}/trends/themes"),
    ("GET", f"{API_PREFIX}/trends/platforms"),
    ("GET", f"{API_PREFIX}/admin/stats"),
    ("POST", f"{API_PREFIX}/admin/scrape"),
    ("DELETE", f"{API_PREFIX}/admin/hackathon/{{id}}"),
]


@dataclass
class CheckResult:
    name: str
    method: str
    path: str
    status: int
    ok: bool
    message: str
    detail: str = ""


@dataclass
class EndpointReport:
    results: list[CheckResult] = field(default_factory=list)
    openapi_missing: list[str] = field(default_factory=list)
    sample_hackathon_id: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    test_email: str | None = None

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok)


def _record(report: EndpointReport, **kwargs) -> CheckResult:
    result = CheckResult(**kwargs)
    report.results.append(result)
    symbol = "PASS" if result.ok else "FAIL"
    print(f"[{symbol}] {result.method} {result.path} -> {result.status} | {result.message}")
    if result.detail:
        print(f"       {result.detail}")
    return result


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {}


def verify_openapi(client: httpx.Client, base_url: str, report: EndpointReport) -> None:
    response = client.get(f"{base_url}/openapi.json")
    if response.status_code != 200:
        _record(
            report,
            name="OpenAPI schema",
            method="GET",
            path="/openapi.json",
            status=response.status_code,
            ok=False,
            message="Could not load OpenAPI schema",
        )
        return

    schema = response.json()
    documented_paths: set[str] = set()
    for path, methods in schema.get("paths", {}).items():
        for method in methods:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                documented_paths.add(f"{method.upper()} {path}")

    _record(
        report,
        name="OpenAPI schema",
        method="GET",
        path="/openapi.json",
        status=200,
        ok=True,
        message=f"Loaded {len(documented_paths)} operations",
    )

    for method, path in EXPECTED_ROUTES:
        normalized = path.replace("{id}", "{hackathon_id}")
        if normalized.startswith("GET /health"):
            continue
        openapi_path = normalized.replace(API_PREFIX, API_PREFIX)
        key = f"{method} {openapi_path}"
        if key not in documented_paths:
            report.openapi_missing.append(key)


def fetch_sample_hackathon_id(client: httpx.Client, base_url: str) -> str | None:
    response = client.get(
        f"{base_url}{API_PREFIX}/hackathons",
        params={"page": 1, "page_size": 1, "only_open": "false"},
    )
    if response.status_code != 200:
        return None
    payload = _json(response)
    items = payload.get("data", {}).get("items", [])
    if items:
        return items[0]["id"]
    return None


def run_checks(base_url: str) -> EndpointReport:
    report = EndpointReport()
    base_url = base_url.rstrip("/")
    test_email = f"api_check_{uuid.uuid4().hex[:8]}@example.com"
    report.test_email = test_email

    with httpx.Client(timeout=30.0) as client:
        verify_openapi(client, base_url, report)

        if report.openapi_missing:
            _record(
                report,
                name="Route inventory",
                method="GET",
                path="/openapi.json",
                status=200,
                ok=False,
                message="Missing documented routes",
                detail=", ".join(report.openapi_missing),
            )
        else:
            _record(
                report,
                name="Route inventory",
                method="GET",
                path="/openapi.json",
                status=200,
                ok=True,
                message="All expected routes are documented",
            )

        response = client.get(f"{base_url}/health")
        payload = _json(response)
        _record(
            report,
            name="Health check",
            method="GET",
            path="/health",
            status=response.status_code,
            ok=response.status_code == 200 and payload.get("success") is True,
            message=payload.get("message", response.text[:120]),
        )

        register_body = {
            "name": "API Check User",
            "email": test_email,
            "password": "TestPass123!",
        }
        response = client.post(f"{base_url}{API_PREFIX}/auth/register", json=register_body)
        payload = _json(response)
        ok = response.status_code == 200 and payload.get("success") is True
        if ok:
            report.access_token = payload["data"]["access_token"]
            report.refresh_token = payload["data"]["refresh_token"]
        _record(
            report,
            name="Register",
            method="POST",
            path=f"{API_PREFIX}/auth/register",
            status=response.status_code,
            ok=ok,
            message=payload.get("message", response.text[:120]),
        )

        response = client.post(
            f"{base_url}{API_PREFIX}/auth/login",
            json={"email": test_email, "password": "TestPass123!"},
        )
        payload = _json(response)
        ok = response.status_code == 200 and payload.get("success") is True
        if ok:
            report.access_token = payload["data"]["access_token"]
            report.refresh_token = payload["data"]["refresh_token"]
        _record(
            report,
            name="Login",
            method="POST",
            path=f"{API_PREFIX}/auth/login",
            status=response.status_code,
            ok=ok,
            message=payload.get("message", response.text[:120]),
        )

        if report.refresh_token:
            response = client.post(
                f"{base_url}{API_PREFIX}/auth/refresh",
                json={"refresh_token": report.refresh_token},
            )
            payload = _json(response)
            ok = response.status_code == 200 and payload.get("success") is True
            if ok:
                report.access_token = payload["data"]["access_token"]
                report.refresh_token = payload["data"]["refresh_token"]
            _record(
                report,
                name="Refresh token",
                method="POST",
                path=f"{API_PREFIX}/auth/refresh",
                status=response.status_code,
                ok=ok,
                message=payload.get("message", response.text[:120]),
            )

        auth_headers = {}
        if report.access_token:
            auth_headers = {"Authorization": f"Bearer {report.access_token}"}

        response = client.get(f"{base_url}{API_PREFIX}/auth/me", headers=auth_headers)
        payload = _json(response)
        _record(
            report,
            name="Auth me",
            method="GET",
            path=f"{API_PREFIX}/auth/me",
            status=response.status_code,
            ok=response.status_code == 200 and payload.get("success") is True,
            message=payload.get("message", response.text[:120]),
        )

        response = client.get(f"{base_url}{API_PREFIX}/users/me", headers=auth_headers)
        payload = _json(response)
        _record(
            report,
            name="Users me GET",
            method="GET",
            path=f"{API_PREFIX}/users/me",
            status=response.status_code,
            ok=response.status_code == 200 and payload.get("success") is True,
            message=payload.get("message", response.text[:120]),
        )

        response = client.patch(
            f"{base_url}{API_PREFIX}/users/me",
            headers=auth_headers,
            json={"name": "API Check Updated", "interests": ["AI", "Web3"]},
        )
        payload = _json(response)
        _record(
            report,
            name="Users me PATCH",
            method="PATCH",
            path=f"{API_PREFIX}/users/me",
            status=response.status_code,
            ok=response.status_code == 200 and payload.get("success") is True,
            message=payload.get("message", response.text[:120]),
        )

        response = client.get(
            f"{base_url}{API_PREFIX}/hackathons",
            params={"page": 1, "page_size": 5, "only_open": "false"},
        )
        payload = _json(response)
        ok = response.status_code == 200 and payload.get("success") is True
        total = payload.get("data", {}).get("total") if ok else None
        _record(
            report,
            name="List hackathons",
            method="GET",
            path=f"{API_PREFIX}/hackathons",
            status=response.status_code,
            ok=ok,
            message=f"{payload.get('message', response.text[:120])} | total={total}",
        )

        response = client.get(
            f"{base_url}{API_PREFIX}/hackathons/search",
            params={"search": "AI", "page": 1, "page_size": 5},
        )
        payload = _json(response)
        _record(
            report,
            name="Search hackathons",
            method="GET",
            path=f"{API_PREFIX}/hackathons/search",
            status=response.status_code,
            ok=response.status_code == 200 and payload.get("success") is True,
            message=payload.get("message", response.text[:120]),
        )

        response = client.get(f"{base_url}{API_PREFIX}/hackathons/trending", params={"limit": 5})
        payload = _json(response)
        _record(
            report,
            name="Trending hackathons",
            method="GET",
            path=f"{API_PREFIX}/hackathons/trending",
            status=response.status_code,
            ok=response.status_code == 200 and payload.get("success") is True,
            message=payload.get("message", response.text[:120]),
        )

        report.sample_hackathon_id = fetch_sample_hackathon_id(client, base_url)
        if report.sample_hackathon_id:
            response = client.get(
                f"{base_url}{API_PREFIX}/hackathons/{report.sample_hackathon_id}"
            )
            payload = _json(response)
            _record(
                report,
                name="Hackathon detail",
                method="GET",
                path=f"{API_PREFIX}/hackathons/{{id}}",
                status=response.status_code,
                ok=response.status_code == 200 and payload.get("success") is True,
                message=payload.get("message", response.text[:120]),
            )
        else:
            _record(
                report,
                name="Hackathon detail",
                method="GET",
                path=f"{API_PREFIX}/hackathons/{{id}}",
                status=0,
                ok=False,
                message="Skipped - no hackathon id available",
            )

        response = client.get(f"{base_url}{API_PREFIX}/themes", params={"limit": 10})
        payload = _json(response)
        _record(
            report,
            name="Themes",
            method="GET",
            path=f"{API_PREFIX}/themes",
            status=response.status_code,
            ok=response.status_code == 200 and payload.get("success") is True,
            message=payload.get("message", response.text[:120]),
        )

        response = client.get(f"{base_url}{API_PREFIX}/platforms")
        payload = _json(response)
        _record(
            report,
            name="Platforms",
            method="GET",
            path=f"{API_PREFIX}/platforms",
            status=response.status_code,
            ok=response.status_code == 200 and payload.get("success") is True,
            message=payload.get("message", response.text[:120]),
        )

        for path_suffix, label in [
            ("/trends/hackathons", "Trends hackathons"),
            ("/trends/themes", "Trends themes"),
            ("/trends/platforms", "Trends platforms"),
        ]:
            response = client.get(f"{base_url}{API_PREFIX}{path_suffix}")
            payload = _json(response)
            _record(
                report,
                name=label,
                method="GET",
                path=f"{API_PREFIX}{path_suffix}",
                status=response.status_code,
                ok=response.status_code == 200 and payload.get("success") is True,
                message=payload.get("message", response.text[:120]),
            )

        if report.sample_hackathon_id and report.access_token:
            hid = report.sample_hackathon_id
            response = client.post(
                f"{base_url}{API_PREFIX}/bookmarks/{hid}",
                headers=auth_headers,
            )
            payload = _json(response)
            _record(
                report,
                name="Create bookmark",
                method="POST",
                path=f"{API_PREFIX}/bookmarks/{{id}}",
                status=response.status_code,
                ok=response.status_code == 200 and payload.get("success") is True,
                message=payload.get("message", response.text[:120]),
            )

            response = client.get(f"{base_url}{API_PREFIX}/bookmarks", headers=auth_headers)
            payload = _json(response)
            _record(
                report,
                name="List bookmarks",
                method="GET",
                path=f"{API_PREFIX}/bookmarks",
                status=response.status_code,
                ok=response.status_code == 200 and payload.get("success") is True,
                message=payload.get("message", response.text[:120]),
            )

            response = client.delete(
                f"{base_url}{API_PREFIX}/bookmarks/{hid}",
                headers=auth_headers,
            )
            payload = _json(response)
            _record(
                report,
                name="Delete bookmark",
                method="DELETE",
                path=f"{API_PREFIX}/bookmarks/{{id}}",
                status=response.status_code,
                ok=response.status_code == 200 and payload.get("success") is True,
                message=payload.get("message", response.text[:120]),
            )

        if report.access_token:
            auth_headers = {"Authorization": f"Bearer {report.access_token}"}

            response = client.get(f"{base_url}{API_PREFIX}/admin/stats", headers=auth_headers)
            payload = _json(response)
            _record(
                report,
                name="Admin stats (non-admin)",
                method="GET",
                path=f"{API_PREFIX}/admin/stats",
                status=response.status_code,
                ok=response.status_code == 403,
                message=payload.get("message", response.text[:120]),
            )

            response = client.post(f"{base_url}{API_PREFIX}/admin/scrape", headers=auth_headers)
            payload = _json(response)
            _record(
                report,
                name="Admin scrape (non-admin)",
                method="POST",
                path=f"{API_PREFIX}/admin/scrape",
                status=response.status_code,
                ok=response.status_code == 403,
                message=payload.get("message", response.text[:120]),
            )

            if report.sample_hackathon_id:
                response = client.delete(
                    f"{base_url}{API_PREFIX}/admin/hackathon/{report.sample_hackathon_id}",
                    headers=auth_headers,
                )
                payload = _json(response)
                _record(
                    report,
                    name="Admin delete hackathon (non-admin)",
                    method="DELETE",
                    path=f"{API_PREFIX}/admin/hackathon/{{id}}",
                    status=response.status_code,
                    ok=response.status_code == 403,
                    message=payload.get("message", response.text[:120]),
                )
        else:
            for method, path, label in [
                ("GET", f"{API_PREFIX}/admin/stats", "Admin stats (skipped)"),
                ("POST", f"{API_PREFIX}/admin/scrape", "Admin scrape (skipped)"),
                ("DELETE", f"{API_PREFIX}/admin/hackathon/{{id}}", "Admin delete (skipped)"),
            ]:
                _record(
                    report,
                    name=label,
                    method=method,
                    path=path,
                    status=0,
                    ok=False,
                    message="Skipped - auth setup incomplete (run database/backend_schema.sql)",
                )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify HackathonFeed API endpoints")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    print(f"Checking API at {args.base_url}\n")
    report = run_checks(args.base_url)
    print("\nSummary")
    print(f"  Passed: {report.passed}")
    print(f"  Failed: {report.failed}")
    if report.failed:
        print("\nFailed checks:")
        for result in report.results:
            if not result.ok:
                print(f"  - {result.method} {result.path}: {result.message}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
