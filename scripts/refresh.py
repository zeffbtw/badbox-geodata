"""Refresh explicitly configured public IOC appendices, preserving source history."""

import argparse
import datetime as dt
import ipaddress
import subprocess
import sys
import tempfile
from pathlib import Path

from geodata import DATA, excluded, json_text, key, load_exclusions, load_records, normalize, read_json, row_order


def download(feed):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'response'
        command = [
            'curl', '--fail', '--silent', '--show-error', '--proto', '=https',
            '--max-time', '45', '--retry', '2', '--retry-max-time', '50',
            '--user-agent', 'Mozilla/5.0', '--max-filesize', str(feed['max_bytes']),
            '--output', str(path), '--write-out', '%{http_code} %{content_type}', feed['url'],
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=100)
        if result.returncode:
            raise ValueError(result.stderr.strip() or f'Download failed (curl {result.returncode})')
        status, _, content_type = result.stdout.partition(' ')
        content_type = content_type.partition(';')[0].lower().strip()
        if status != '200' or content_type not in feed['content_types']:
            raise ValueError(f'Unexpected response: HTTP {status}, {content_type}')
        body = path.read_bytes()
    if not body or len(body) > feed['max_bytes']:
        raise ValueError(f'Unexpected response size: {len(body)} bytes')
    return body

def extract(feed, body):
    if feed['format'] == 'pdf':
        if not body.startswith(b'%PDF-'):
            raise ValueError('Expected a PDF document')
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source.pdf'
            source.write_bytes(body)
            result = subprocess.run(
                ['pdftotext', '-layout', str(source), '-'],
                check=True, capture_output=True, text=True, encoding='utf-8', timeout=60,
            )
        return result.stdout
    contents = body.decode('utf-8-sig', errors='strict')
    if feed['format'] == 'csv' and contents.lstrip().startswith('<'):
        raise ValueError('Received HTML in place of CSV')
    return contents


def reconcile(feeds, parsers, fetch, data=DATA):
    history_file = data / 'feed-state.json'
    append_file = data / 'badbox-refresh.json'
    history = read_json(history_file) if history_file.exists() else {}
    additions = read_json(append_file) if append_file.exists() else []
    prior = {key(row) for row in load_records(data)}
    exclusions = load_exclusions(data)
    today = dt.datetime.now(dt.UTC).date().isoformat()
    feed_ids = {feed['id'] for feed in feeds}
    if len(feed_ids) != len(feeds):
        raise ValueError('Repeated feed ID')
    if unknown := set(history) - feed_ids:
        raise ValueError(f'Unexpected removal of configured feeds: {", ".join(sorted(unknown))}')
    snapshots = dict(history)
    for feed in feeds:
        feed_id, source = feed['id'], feed['url']
        try:
            raw = fetch(feed)
            if raw is None:
                continue
            rows = parsers[feed_id](extract(feed, raw))
            observed = set()
            for row in rows:
                value = normalize(row['indicator'], row['kind'])
                item = row['kind'], value
                if item in observed:
                    raise ValueError(f'Duplicate normalized indicator {value}')
                observed.add(item)
                if excluded(exclusions, row['kind'], value, source):
                    continue
                record = dict(row, indicator=value, source=source, variant=feed['variant'], added=today)
                if key(record) not in prior:
                    if row['kind'] == 'ip':
                        network = ipaddress.ip_network(value)
                        narrow = row['match'] == 'ip' and network.prefixlen == network.max_prefixlen
                    else:
                        narrow = row['match'] == 'full'
                    if not narrow:
                        raise ValueError(f'Expanded scope requires manual review: {value}')
                    additions.append(record)
                    prior.add(key(record))
            if len(observed) < feed['minimum']:
                raise ValueError(f'Too few IOC rows: {len(observed)} (expected at least {feed["minimum"]})')
            removed = {tuple(item) for item in history.get(feed_id, [])} - observed
            unexplained = sorted(value for kind, value in removed if not excluded(exclusions, kind, value, source))
            if unexplained:
                preview = ', '.join(unexplained[:10])
                raise ValueError(f'{len(unexplained)} previously seen indicators missing: {preview}. Review before publishing.')
            snapshots[feed_id] = sorted([kind, value] for kind, value in observed)
            print(f'{feed_id}: {len(observed)} verified source indicators')
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
            raise ValueError(f'{feed_id} ({source}): {exc}') from exc
    return snapshots, sorted(additions, key=row_order)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-dir', type=Path, help='Prefer captured source files named after feed IDs')
    args = parser.parse_args()
    try:
        from feed_badbox12 import parse_h5, parse_original
        from feed_badbox3 import parse as parse_badbox3

        feeds = read_json(DATA / 'feeds.json')
        if args.snapshot_dir and not any(
                (args.snapshot_dir / (feed['id'] + '.' + feed['format'])).is_file() for feed in feeds):
            raise ValueError(f'No configured snapshots found in {args.snapshot_dir}')
        parsers = {'human-badbox': parse_original, 'human-badbox2-h5': parse_h5, 'human-badbox3': parse_badbox3}
        def fetch(feed):
            if args.snapshot_dir:
                snapshot = args.snapshot_dir / (feed['id'] + '.' + feed['format'])
                if snapshot.is_file():
                    return snapshot.read_bytes()
            if feed['automatic']:
                return download(feed)
            return None
        snapshots, additions = reconcile(feeds, parsers, fetch)
        for name, contents in (('feed-state.json', snapshots), ('badbox-refresh.json', additions)):
            path = DATA / name
            candidate = json_text(contents)
            if not path.exists() or path.read_text(encoding='utf-8') != candidate:
                path.write_text(candidate, encoding='utf-8')
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(f'Refresh rejected: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
