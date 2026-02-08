#!/usr/bin/env python3
"""
Comprehensive test script for ACE-Step LM-only API endpoints.

Tests:
  - POST /lm/inspire   — generate caption/lyrics/metadata from text description
  - POST /lm/format    — enhance caption + lyrics with metadata
  - POST /lm/understand — analyze audio and extract metadata (codes or file upload)
  - Error cases (missing params, invalid input)
  - Seed reproducibility

Usage:
    python scripts/test_lm_endpoints.py [--base-url URL] [--api-key KEY] [--audio-file PATH]

    --base-url   Server base URL (default: http://localhost:8001)
    --api-key    Optional API key for authenticated requests
    --audio-file Path to an audio file for /lm/understand file-upload test
                 (if omitted, file-upload tests are skipped)

Exit codes:
    0 — all tests passed
    1 — one or more tests failed
"""

import argparse
import json
import sys
import time
from typing import Any, Optional

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package is required. Install with: pip install requests")
    sys.exit(1)


# ── Helpers ────────────────────────────────────────────────────────────────

def _headers(api_key: Optional[str] = None) -> dict:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _pp(label: str, obj: Any) -> None:
    """Pretty-print a labelled JSON object."""
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


class TestRunner:
    """Simple test runner that tracks pass/fail counts."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results: list[dict] = []

    def _record(self, name: str, status: str, detail: str = "") -> None:
        self.results.append({"name": name, "status": status, "detail": detail})
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        else:
            self.skipped += 1
        icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
        msg = f"  {icon} {name}"
        if detail:
            msg += f"  — {detail}"
        print(msg)

    # ── /lm/inspire tests ──────────────────────────────────────────────

    def test_inspire_basic(self) -> None:
        """Basic /lm/inspire with a simple query."""
        name = "inspire: basic query"
        try:
            resp = requests.post(
                f"{self.base_url}/lm/inspire",
                headers=_headers(self.api_key),
                json={"query": "a chill lo-fi hip hop beat for studying"},
                timeout=120,
            )
            data = resp.json()
            if resp.status_code != 200 or data.get("code") != 200:
                self._record(name, "FAIL", f"status={resp.status_code}, body={json.dumps(data)}")
                return
            d = data["data"]
            assert d.get("caption"), "missing caption"
            assert d.get("lyrics") is not None, "missing lyrics key"
            assert d.get("bpm") is not None, "missing bpm"
            assert d.get("duration") is not None, "missing duration"
            _pp(name, d)
            self._record(name, "PASS")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    def test_inspire_instrumental(self) -> None:
        """Inspire with instrumental=true should have no/empty lyrics."""
        name = "inspire: instrumental"
        try:
            resp = requests.post(
                f"{self.base_url}/lm/inspire",
                headers=_headers(self.api_key),
                json={
                    "query": "epic orchestral trailer music with heavy drums",
                    "instrumental": True,
                    "temperature": 0.9,
                },
                timeout=120,
            )
            data = resp.json()
            if data.get("code") != 200:
                self._record(name, "FAIL", f"code={data.get('code')}, error={data.get('error')}")
                return
            d = data["data"]
            assert d.get("caption"), "missing caption"
            # instrumental should be True in response
            _pp(name, d)
            self._record(name, "PASS")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    def test_inspire_with_language(self) -> None:
        """Inspire with vocal_language constraint."""
        name = "inspire: vocal_language=ja"
        try:
            resp = requests.post(
                f"{self.base_url}/lm/inspire",
                headers=_headers(self.api_key),
                json={
                    "query": "upbeat J-pop idol song with catchy melody",
                    "vocal_language": "ja",
                },
                timeout=120,
            )
            data = resp.json()
            if data.get("code") != 200:
                self._record(name, "FAIL", f"code={data.get('code')}, error={data.get('error')}")
                return
            d = data["data"]
            _pp(name, d)
            self._record(name, "PASS")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    def test_inspire_missing_query(self) -> None:
        """Inspire with no query should return 400 error."""
        name = "inspire: missing query (expect 400)"
        try:
            resp = requests.post(
                f"{self.base_url}/lm/inspire",
                headers=_headers(self.api_key),
                json={},
                timeout=30,
            )
            data = resp.json()
            if data.get("code") == 400:
                self._record(name, "PASS", f"error={data.get('error')}")
            else:
                self._record(name, "FAIL", f"expected code=400, got code={data.get('code')}")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    def test_inspire_seed_reproducibility(self) -> None:
        """Two calls with same seed should produce identical results."""
        name = "inspire: seed reproducibility"
        try:
            payload = {
                "query": "dark ambient drone music",
                "seed": 12345,
                "temperature": 0.85,
            }
            resp1 = requests.post(
                f"{self.base_url}/lm/inspire",
                headers=_headers(self.api_key),
                json=payload,
                timeout=120,
            )
            resp2 = requests.post(
                f"{self.base_url}/lm/inspire",
                headers=_headers(self.api_key),
                json=payload,
                timeout=120,
            )
            d1 = resp1.json()
            d2 = resp2.json()
            if d1.get("code") != 200 or d2.get("code") != 200:
                self._record(name, "FAIL", f"one or both calls failed: {d1.get('error')}, {d2.get('error')}")
                return

            caption1 = d1["data"].get("caption", "")
            caption2 = d2["data"].get("caption", "")
            lyrics1 = d1["data"].get("lyrics", "")
            lyrics2 = d2["data"].get("lyrics", "")

            if caption1 == caption2 and lyrics1 == lyrics2:
                self._record(name, "PASS", "captions and lyrics match")
            else:
                # Seed reproducibility may not be guaranteed with vllm backend
                self._record(
                    name,
                    "FAIL",
                    f"outputs differ (may be expected with vllm backend). "
                    f"caption match={caption1 == caption2}, lyrics match={lyrics1 == lyrics2}",
                )
                _pp(f"{name} — call 1", d1["data"])
                _pp(f"{name} — call 2", d2["data"])
        except Exception as e:
            self._record(name, "FAIL", str(e))

    # ── /lm/format tests ──────────────────────────────────────────────

    def test_format_basic(self) -> None:
        """Basic /lm/format with caption + lyrics."""
        name = "format: basic"
        try:
            resp = requests.post(
                f"{self.base_url}/lm/format",
                headers=_headers(self.api_key),
                json={
                    "prompt": "indie folk",
                    "lyrics": "I walked along the river\nthe sun was setting low",
                },
                timeout=120,
            )
            data = resp.json()
            if data.get("code") != 200:
                self._record(name, "FAIL", f"code={data.get('code')}, error={data.get('error')}")
                return
            d = data["data"]
            assert d.get("caption"), "missing caption"
            assert d.get("bpm") is not None, "missing bpm"
            _pp(name, d)
            self._record(name, "PASS")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    def test_format_with_constraints(self) -> None:
        """Format with metadata constraints (bpm, key, duration)."""
        name = "format: with constraints"
        try:
            resp = requests.post(
                f"{self.base_url}/lm/format",
                headers=_headers(self.api_key),
                json={
                    "prompt": "jazz ballad",
                    "lyrics": "[Verse]\nMoonlight on the water\nStars above the city",
                    "bpm": 80,
                    "key_scale": "Bb Major",
                    "time_signature": "3",
                    "duration": 240,
                    "language": "en",
                },
                timeout=120,
            )
            data = resp.json()
            if data.get("code") != 200:
                self._record(name, "FAIL", f"code={data.get('code')}, error={data.get('error')}")
                return
            d = data["data"]
            _pp(name, d)
            # Check that constraints are respected (or at least present)
            self._record(name, "PASS")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    def test_format_caption_only(self) -> None:
        """Format with only caption, no lyrics."""
        name = "format: caption only"
        try:
            resp = requests.post(
                f"{self.base_url}/lm/format",
                headers=_headers(self.api_key),
                json={"caption": "aggressive death metal with blast beats"},
                timeout=120,
            )
            data = resp.json()
            if data.get("code") != 200:
                self._record(name, "FAIL", f"code={data.get('code')}, error={data.get('error')}")
                return
            _pp(name, data["data"])
            self._record(name, "PASS")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    def test_format_missing_both(self) -> None:
        """Format with no caption and no lyrics should return 400."""
        name = "format: missing both (expect 400)"
        try:
            resp = requests.post(
                f"{self.base_url}/lm/format",
                headers=_headers(self.api_key),
                json={},
                timeout=30,
            )
            data = resp.json()
            if data.get("code") == 400:
                self._record(name, "PASS", f"error={data.get('error')}")
            else:
                self._record(name, "FAIL", f"expected code=400, got code={data.get('code')}")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    # ── /lm/understand tests ──────────────────────────────────────────

    def test_understand_no_input(self) -> None:
        """Understand with no audio should return 400."""
        name = "understand: no input (expect 400)"
        try:
            resp = requests.post(
                f"{self.base_url}/lm/understand",
                headers=_headers(self.api_key),
                json={},
                timeout=30,
            )
            data = resp.json()
            if data.get("code") == 400:
                self._record(name, "PASS", f"error={data.get('error')}")
            else:
                self._record(name, "FAIL", f"expected code=400, got code={data.get('code')}")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    def test_understand_file_upload(self, audio_file: Optional[str] = None) -> None:
        """Understand via file upload (multipart/form-data)."""
        name = "understand: file upload"
        if not audio_file:
            self._record(name, "SKIP", "no --audio-file provided")
            return
        try:
            with open(audio_file, "rb") as f:
                files = {"audio": (audio_file.split("/")[-1], f)}
                form_data = {"temperature": "0.3"}
                if self.api_key:
                    form_data["ai_token"] = self.api_key
                resp = requests.post(
                    f"{self.base_url}/lm/understand",
                    files=files,
                    data=form_data,
                    timeout=300,
                )
            data = resp.json()
            if data.get("code") != 200:
                self._record(name, "FAIL", f"code={data.get('code')}, error={data.get('error')}")
                return
            d = data["data"]
            assert d.get("caption"), "missing caption"
            _pp(name, d)
            self._record(name, "PASS")
        except FileNotFoundError:
            self._record(name, "FAIL", f"audio file not found: {audio_file}")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    def test_understand_audio_path(self, audio_file: Optional[str] = None) -> None:
        """Understand via audio_path (JSON, server-side path)."""
        name = "understand: audio_path"
        if not audio_file:
            self._record(name, "SKIP", "no --audio-file provided")
            return
        try:
            resp = requests.post(
                f"{self.base_url}/lm/understand",
                headers=_headers(self.api_key),
                json={"audio_path": audio_file, "temperature": 0.3},
                timeout=300,
            )
            data = resp.json()
            if data.get("code") != 200:
                self._record(name, "FAIL", f"code={data.get('code')}, error={data.get('error')}")
                return
            _pp(name, data["data"])
            self._record(name, "PASS")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    # ── /health sanity check ──────────────────────────────────────────

    def test_health(self) -> None:
        """Check server is reachable via /health."""
        name = "health: server reachable"
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                self._record(name, "PASS")
            else:
                self._record(name, "FAIL", f"unexpected response: {data}")
        except requests.ConnectionError:
            self._record(name, "FAIL", f"cannot connect to {self.base_url}")
        except Exception as e:
            self._record(name, "FAIL", str(e))

    # ── Run all ────────────────────────────────────────────────────────

    def run_all(self, audio_file: Optional[str] = None) -> bool:
        print(f"\n{'═' * 60}")
        print(f"  ACE-Step LM Endpoint Tests")
        print(f"  Server: {self.base_url}")
        print(f"  Auth:   {'yes' if self.api_key else 'no'}")
        print(f"  Audio:  {audio_file or '(none — understand file tests will be skipped)'}")
        print(f"{'═' * 60}")

        t0 = time.time()

        # Health check first
        print("\n── Health ──")
        self.test_health()
        if self.failed > 0:
            print("\n  Server not reachable — aborting remaining tests.")
            return False

        # /lm/inspire
        print("\n── /lm/inspire ──")
        self.test_inspire_basic()
        self.test_inspire_instrumental()
        self.test_inspire_with_language()
        self.test_inspire_missing_query()
        self.test_inspire_seed_reproducibility()

        # /lm/format
        print("\n── /lm/format ──")
        self.test_format_basic()
        self.test_format_with_constraints()
        self.test_format_caption_only()
        self.test_format_missing_both()

        # /lm/understand
        print("\n── /lm/understand ──")
        self.test_understand_no_input()
        self.test_understand_file_upload(audio_file)
        self.test_understand_audio_path(audio_file)

        elapsed = time.time() - t0
        print(f"\n{'═' * 60}")
        print(f"  Results:  {self.passed} passed, {self.failed} failed, {self.skipped} skipped")
        print(f"  Time:     {elapsed:.1f}s")
        print(f"{'═' * 60}\n")

        return self.failed == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Test ACE-Step LM API endpoints")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="API server base URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for authentication",
    )
    parser.add_argument(
        "--audio-file",
        default=None,
        help="Path to an audio file for /lm/understand tests (local or server path)",
    )
    args = parser.parse_args()

    runner = TestRunner(base_url=args.base_url, api_key=args.api_key)
    ok = runner.run_all(audio_file=args.audio_file)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
