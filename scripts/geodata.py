"""Input validation and the Xray GeoSite/GeoIP protobuf wire format."""

import datetime as dt
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DIST = ROOT / 'dist'
VARIANTS = {'BADBOX', 'BADBOX 2.0', 'BADBOX 3.0'}
MATCH_TYPES = {'domain': 2, 'full': 3}
LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z')
SHARED = {'aliyuncs.com', 'amazonaws.com', 'azurewebsites.net', 'blogspot.com',
          'cloudfront.net', 'cloudfunctions.net', 'github.com', 'github.io',
          'githubusercontent.com', 'google.com', 'googleusercontent.com',
          'herokuapp.com', 'netlify.app', 'pages.dev', 'vercel.app', 'workers.dev'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def normalize(value, kind):
    if not isinstance(value, str):
        raise ValueError(f'Expected a string indicator, got {value!r}')
    value = value.strip().lower().replace('[.]', '.')
    if kind == 'ip':
        network = ipaddress.ip_network(value, strict=True)
        if not network.is_global or network.is_multicast or '%' in value:
            raise ValueError(f'Expected a public unicast IP network, got {value!r}')
        return str(network)
    if kind != 'domain' or re.search(r'[/:@?#%\\\s]', value):
        raise ValueError(f'Expected a hostname, got {value!r}')
    value = value.removesuffix('.').encode('idna').decode('ascii')
    labels = value.split('.')
    if (len(labels) < 2 or len(value) > 253 or labels[-1].isdigit()
            or not all(LABEL.fullmatch(label) for label in labels)):
        raise ValueError(f'Invalid domain: {value!r}')
    return value


def valid_source(value):
    url = urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ValueError(f'Expected a public HTTPS source, got {value!r}')


def key(row):
    return row['kind'], row['indicator'], row['source']


def row_order(row):
    return row['kind'], row['indicator'], row['source'], row['variant']


def load_records(data=DATA):
    rows = []
    for path in sorted(data.glob('badbox-*.json')):
        for row in read_json(path):
            row['indicator'] = normalize(row['indicator'], row['kind'])
            valid_source(row['source'])
            if row['variant'] not in VARIANTS or not row['role'].strip():
                raise ValueError(f'Invalid provenance in {path.name}: {row!r}')
            dt.date.fromisoformat(row['added'])
            target = row['indicator']
            if row['kind'] == 'domain':
                mode = row['match']
                if mode not in MATCH_TYPES:
                    raise ValueError(f'Unknown match type for {target}: {mode!r}')
                if target in SHARED or (mode == 'domain' and any(
                        target.endswith('.' + shared) for shared in SHARED)):
                    raise ValueError(f'Shared platform requires an exact endpoint: {target}')
                if mode == 'domain' and not row.get('scope_evidence', '').strip():
                    raise ValueError(f'Missing evidence for subdomain coverage: {target}')
            else:
                network = ipaddress.ip_network(target)
                if row['match'] != 'ip':
                    raise ValueError(f'Wrong match type for IP {target}')
                if network.prefixlen != network.max_prefixlen and not row.get('scope_evidence', '').strip():
                    raise ValueError(f'Missing source evidence for IP range: {target}')
            rows.append(row)
    if len({key(row) for row in rows}) != len(rows):
        raise ValueError('Duplicate indicator and source records')
    return sorted(rows, key=row_order)


def load_exclusions(data=DATA):
    exclusions = []
    for path in sorted(data.glob('exclusions-*.json')):
        for row in read_json(path):
            valid_source(row['source'])
            if row['variant'] not in VARIANTS or not row['reason'].strip() or not row['indicator'].strip():
                raise ValueError(f'Invalid exclusion in {path.name}: {row!r}')
            exclusions.append(row)
    return sorted(exclusions, key=lambda row: (row['variant'], row['indicator'], row['source']))


def excluded(exclusions, kind, indicator, source):
    for row in exclusions:
        if row['source'] != source:
            continue
        try:
            candidate = normalize(row['indicator'], kind)
        except ValueError:
            continue
        if candidate == indicator:
            return True
    return False


def varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    return varint(number << 3 | 2) + varint(len(value)) + value


def encode(rules):
    entry = field(1, b'BADBOX')
    return field(1, entry + b''.join(field(2, rule) for rule in rules))


def fields(payload):
    """Read only the two wire types used by this project's schema."""
    pos = 0

    def take_varint():
        nonlocal pos
        value = 0
        for shift in range(0, 70, 7):
            if pos == len(payload):
                break
            byte = payload[pos]
            pos += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError('Invalid protobuf varint')

    while pos < len(payload):
        tag = take_varint()
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            yield number, take_varint()
        elif wire == 2:
            length = take_varint()
            end = pos + length
            if end > len(payload):
                raise ValueError('Truncated protobuf field')
            yield number, payload[pos:end]
            pos = end
        else:
            raise ValueError(f'Unexpected protobuf field type {wire}')


def read_category(payload):
    outer = list(fields(payload))
    if len(outer) != 1 or outer[0][0] != 1:
        raise ValueError('Expected exactly one GeoData category')
    category, *rules = fields(outer[0][1])
    if category != (1, b'BADBOX') or not rules or any(number != 2 for number, _ in rules):
        raise ValueError('Expected nonempty BADBOX category with no extra fields')
    return [list(fields(rule)) for _, rule in rules]
