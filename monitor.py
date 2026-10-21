#!/usr/bin/env python3
"""PUMA product stock monitor with email notifications.

The monitoring-loop/state pattern is adapted from common open-source stock
monitors. PUMA-specific detection reads schema.org Product/Offer JSON-LD first
and falls back to visible page text.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
STATE_FILE = ROOT / "state.json"
LOG_FILE = ROOT / "monitor.log"


class JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capturing = False
        self._buffer: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag.lower() == "script" and attributes.get("type") == "application/ld+json":
            self._capturing = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capturing:
            self.blocks.append("".join(self._buffer))
            self._capturing = False
            self._buffer = []


def load_env(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def log(message: str) -> None:
    line = f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] {message}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_state(state: dict[str, Any]) -> None:
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def product_from_json_ld(raw_blocks: list[str]) -> dict[str, Any] | None:
    def walk(value: Any):
        if isinstance(value, dict):
            if value.get("@type") == "Product":
                yield value
            graph = value.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)

    for raw in raw_blocks:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for product in walk(payload):
            return product
    return None


def normalize_offer(offers: Any) -> dict[str, Any]:
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return offers if isinstance(offers, dict) else {}


def check_product(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urlopen(request, timeout=45) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"PUMA request failed: {exc}") from exc

    parser = JsonLdParser()
    parser.feed(html)
    raw_blocks = parser.blocks
    visible_text = html

    product = product_from_json_ld(raw_blocks)
    if product:
        offer = normalize_offer(product.get("offers"))
        availability = str(offer.get("availability", ""))
        if availability:
            in_stock = availability.rstrip("/").endswith("InStock")
            return {
                "in_stock": in_stock,
                "availability": availability.rsplit("/", 1)[-1],
                "name": product.get("name") or "PUMA product",
                "sku": product.get("sku"),
                "price": offer.get("price"),
                "currency": offer.get("priceCurrency"),
                "source": "schema.org JSON-LD",
            }

    text = visible_text.lower()
    if "sold out" in text or "out of stock" in text:
        in_stock = False
        availability = "OutOfStock"
    elif "add to cart" in text or "add to bag" in text:
        in_stock = True
        availability = "InStock"
    else:
        raise RuntimeError("Could not determine stock state from JSON-LD or visible text")

    return {
        "in_stock": in_stock,
        "availability": availability,
        "name": "PUMA product",
        "sku": None,
        "price": None,
        "currency": None,
        "source": "visible text fallback",
    }


def smtp_settings() -> dict[str, Any]:
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError("Missing email settings: " + ", ".join(missing))
    return {
        "host": os.environ["SMTP_HOST"],
        "port": int(os.environ["SMTP_PORT"]),
        "user": os.environ["SMTP_USER"],
        "password": os.environ["SMTP_PASSWORD"],
        "to": os.environ["EMAIL_TO"],
        "from": os.getenv("EMAIL_FROM", os.environ["SMTP_USER"]),
        "ssl": env_bool("SMTP_SSL", True),
    }


def send_email(subject: str, body: str) -> None:
    config = smtp_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["from"]
    message["To"] = config["to"]
    message.set_content(body)

    if config["ssl"]:
        with smtplib.SMTP_SSL(
            config["host"], config["port"], context=ssl.create_default_context(), timeout=30
        ) as smtp:
            smtp.login(config["user"], config["password"])
            smtp.send_message(message)
    else:
        with smtplib.SMTP(config["host"], config["port"], timeout=30) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(config["user"], config["password"])
            smtp.send_message(message)


def notify_restock(result: dict[str, Any], url: str) -> None:
    price = ""
    if result.get("price") is not None:
        price = f"\nPrice: {result.get('currency', '')} {result['price']}"
    send_email(
        f"PUMA restock: {result['name']}",
        (
            "The monitored PUMA product is now in stock.\n\n"
            f"Product: {result['name']}\n"
            f"SKU: {result.get('sku') or 'Unknown'}"
            f"{price}\n"
            f"Status: {result['availability']}\n"
            f"Detected via: {result['source']}\n\n"
            f"Buy now: {url}\n"
        ),
    )


def should_notify(previous: bool | None, current: bool) -> bool:
    """Notify on OutOfStock -> InStock and on first-ever InStock check."""
    return current and previous is not True


def write_github_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        raise RuntimeError("GITHUB_OUTPUT is unavailable outside GitHub Actions")
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def parse_cloud_previous_state() -> bool | None:
    value = os.getenv("PREVIOUS_STOCK_STATE", "").strip().lower()
    if value == "instock":
        return True
    if value == "outofstock":
        return False
    return None


def run_github_actions_check(url: str) -> dict[str, Any]:
    """Run one stateless cloud check and emit the state for repository storage."""
    result = check_product(url)
    previous_in_stock = parse_cloud_previous_state()
    log(
        f"cloud status={result['availability']} name={result['name']!r} "
        f"sku={result.get('sku')} source={result['source']}"
    )

    if should_notify(previous_in_stock, result["in_stock"]):
        notify_restock(result, url)
        log("cloud restock email sent")

    # Emitted only after any required email succeeds. A failed email therefore
    # leaves the repository state unchanged so the next run retries it.
    write_github_output("stock_state", result["availability"])
    write_github_output("sku", str(result.get("sku") or ""))
    return result


def run_check(url: str) -> dict[str, Any]:
    result = check_product(url)
    previous = read_state()
    previous_in_stock = previous.get("in_stock")
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    log(
        f"status={result['availability']} name={result['name']!r} "
        f"sku={result.get('sku')} source={result['source']}"
    )

    notify = should_notify(previous_in_stock, result["in_stock"])
    if previous_in_stock is None and not env_bool("NOTIFY_ON_FIRST_IN_STOCK", True):
        notify = False
    if notify:
        notify_restock(result, url)
        log("restock email sent")

    write_state({**result, "url": url, "checked_at": now})
    return result


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Monitor a PUMA product and email on restock")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument(
        "--github-actions",
        action="store_true",
        help="Run once using PREVIOUS_STOCK_STATE and emit outputs for GitHub Actions",
    )
    parser.add_argument("--test-email", action="store_true", help="Send a test email and exit")
    args = parser.parse_args()

    if args.test_email:
        send_email("PUMA monitor test", "Email notifications are configured correctly.")
        log("test email sent")
        return 0

    url = os.getenv("PRODUCT_URL")
    if not url:
        print("PRODUCT_URL is missing from .env", file=sys.stderr)
        return 2
    interval = max(180, int(os.getenv("CHECK_INTERVAL_SECONDS", "300")))

    if args.github_actions:
        run_github_actions_check(url)
        return 0

    while True:
        try:
            run_check(url)
        except Exception as exc:
            log(f"check failed: {exc}")
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
