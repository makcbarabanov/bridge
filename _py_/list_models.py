#!/usr/bin/env python3
"""Список моделей Gemini для текущего API-ключа (GET .../v1beta/models)."""
import json
import os
import socket
import sys
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def _force_ipv4() -> None:
    # Иначе urllib может пойти по IPv6 — у Google для v6 часто «User location is not supported»,
    # хотя IPv4 с того же хоста (US) проходит.
    orig = socket.getaddrinfo

    def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        return orig(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _ipv4_only  # type: ignore[assignment]


def main() -> None:
    key = (
        (os.environ.get("PRIMARY_API_KEY") or "").strip()
        or os.environ.get("GOOGLE_AI_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not key:
        print("Задай GOOGLE_AI_KEY или GOOGLE_API_KEY в окружении / .env", file=sys.stderr)
        sys.exit(1)

    _force_ipv4()

    base = "https://generativelanguage.googleapis.com/v1beta/models"
    url = f"{base}?key={key}"

    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            data = json.loads(body)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.reason}", file=sys.stderr)
        err_body = e.read().decode() if e.fp else ""
        print(err_body, file=sys.stderr)
        sys.exit(1)

    models = data.get("models") or []
    print(f"Всего моделей: {len(models)}\n")
    for m in models:
        name = m.get("name", "")
        methods = m.get("supportedGenerationMethods") or []
        # Показываем только то, что умеет generateContent
        if "generateContent" in methods:
            short = name.replace("models/", "") if name.startswith("models/") else name
            print(f"  {short}")
            print(f"    name: {name}")
            print(f"    methods: {methods}")
            print()


if __name__ == "__main__":
    main()
