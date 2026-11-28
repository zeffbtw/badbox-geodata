"""Read the exact MoYu C2 hosts from Nokia Deepfield's IOC CSV."""

import csv
import datetime as dt
import io

from geodata import normalize

HEADER = ['domain', 'c2_method', 'first_seen', 'status', 'notes']
C2_METHODS = {
    'badbox-a1-config': ('a1.', 'MoYu client configuration C2'),
    'badbox-t1-cpc': ('t1.', 'MoYu task and proxy C2'),
}
STATUS = {'active', 'inactive', 'dead', 'unknown'}


def parse_domains(text):
    reader = csv.reader(io.StringIO(text), strict=True)
    records = []
    seen = set()
    try:
        if next(reader, None) != HEADER:
            raise ValueError('Nokia domains CSV: unexpected header')
        for row in reader:
            if len(row) != len(HEADER):
                raise ValueError(f'Nokia domains CSV line {reader.line_num}: unexpected row shape')
            host, method, first_seen, status, notes = row
            if status not in STATUS:
                raise ValueError(f'Nokia domains CSV line {reader.line_num}: unknown status {status!r}')
            if method not in C2_METHODS or status == 'unknown':
                continue
            host = normalize(host, 'domain')
            prefix, role = C2_METHODS[method]
            observed = dt.date.fromisoformat(first_seen + '-01')
            if not host.startswith(prefix) or host.count('.') < 2 or observed.isoformat()[:7] != first_seen or not notes.strip():
                raise ValueError(f'Nokia domains CSV line {reader.line_num}: invalid evidence for {host}')
            if host in seen:
                raise ValueError(f'Nokia domains CSV line {reader.line_num}: repeated C2 host {host}')
            seen.add(host)
            records.append({'indicator': host, 'kind': 'domain', 'match': 'full',
                            'role': role, 'first_seen': first_seen})
    except csv.Error as error:
        raise ValueError(f'Nokia domains CSV line {reader.line_num}: {error}') from error
    return records
