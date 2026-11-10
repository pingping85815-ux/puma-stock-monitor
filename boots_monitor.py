"""Boots-only check; reuse the existing monitor's HTTP/parser/SMTP infrastructure."""
import json
import os
from datetime import datetime
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import monitor

URL = 'https://www.boots.com/chanel-la-mousse-camellia-cleanser-150ml-10366258'
NAME = 'CHANEL La Mousse Camellia Cleanser 150ml'
UNKNOWN = 'UNKNOWN'


def detect(html):
    parser = monitor.JsonLdParser()
    parser.feed(html)
    statuses = []

    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            kind = value.get('@type', [])
            if kind == 'Product' or isinstance(kind, list) and 'Product' in kind:
                yield value
            for child in value.values():
                if isinstance(child, (dict, list)):
                    yield from walk(child)

    for raw in parser.blocks:
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            continue
        for product in walk(payload):
            # Require the exact page identity and size; never select the first offer
            # from a group of variants or use recommended products' availability.
            identity = product.get('url', product.get('@id', ''))
            if not isinstance(identity, str) or urlsplit(identity).path != urlsplit(URL).path:
                continue
            name = str(product.get('name', '')).lower().replace(' ', '')
            if not all(token in name for token in ('chanel', 'camellia', '150ml')):
                continue
            offers = product.get('offers')
            if isinstance(offers, list):
                if len(offers) != 1:
                    return UNKNOWN
                offers = offers[0]
            if not isinstance(offers, dict):
                return UNKNOWN
            availability = offers.get('availability')
            statuses.append({
                'https://schema.org/InStock': 'IN_STOCK',
                'http://schema.org/InStock': 'IN_STOCK',
                'https://schema.org/OutOfStock': 'OUT_OF_STOCK',
                'http://schema.org/OutOfStock': 'OUT_OF_STOCK',
            }.get(availability, UNKNOWN))
    return statuses[0] if statuses and len(set(statuses)) == 1 else UNKNOWN


def check():
    try:
        request = Request(URL, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-GB,en;q=0.9'})
        with urlopen(request, timeout=30) as response:
            if response.status != 200 or response.url.split('?')[0] != URL:
                return UNKNOWN
            return detect(response.read().decode('utf-8', errors='replace'))
    except Exception as exc:
        print(f'Boots request UNKNOWN: {type(exc).__name__}')
        return UNKNOWN


def run():
    current = check()
    previous = os.getenv('PREVIOUS_STOCK_STATE', '')
    now = datetime.now(ZoneInfo('Europe/London')).isoformat(timespec='seconds')
    print(f'Boots {current} at {now}')
    if previous == 'OUT_OF_STOCK' and current == 'IN_STOCK':
        monitor.send_email(f'Boots restock: {NAME}',
                           f'Product: {NAME}\nURL: {URL}\nDetected (UK): {now}\nStatus: {current}\n')
    # Unknown observations never overwrite the last confirmed stock state.
    # Emit only after SMTP succeeds, so failures can be retried.
    monitor.write_github_output('stock_state', current)
    return current


if __name__ == '__main__':
    run()
