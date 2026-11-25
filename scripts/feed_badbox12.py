"""Parse the original BADBOX C2 and BADBOX 2.0 H5 appendices from HUMAN."""

import csv
import io
import re
from pathlib import Path


ORIGINAL_SOURCE = 'https://www.humansecurity.com/hubfs/HUMAN_Report_BADBOX-and-PEACHPIT.pdf'
H5_SOURCE = 'https://www.humansecurity.com/wp-content/uploads/2025/03/BADBOX-2-H5-Domain-List.csv'
H5_ROLE = 'Хост рекламного мошенничества (BADBOX 2.0 Hidden WebViews/H5)'
_ROOT_ZONES = Path(__file__).resolve().parent.parent / 'data' / 'iana-tlds.txt'
_KNOWN_NON_DNS = {'fivemobile.thescore', 'hgtv.watcher', 'zalivka.animation2'}
_LABEL = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
_HOST = re.compile(rf'{_LABEL}(?:\.{_LABEL})+')
_ORIGINAL_HEADING = re.compile(
    r'^Appendix: Indicators of Compromise \(continued\)[ \t]*\n'
    r'C2 Servers[ \t]*\n[ \t]*Domain[ \t]+Operation[ \t]*\n', re.MULTILINE,
)
_ORIGINAL_ROLES = {
    'cbphe.com': 'Первичный C2 и загрузка компонентов',
    'cbpheback.com': 'Вторичный C2 и обновления',
}
_PEACHPIT_SCOPE = (
    'В приложении HUMAN указана инфраструктура C2 PEACHPIT, а в тексте отчёта (стр. 23–24) '
    'описаны загрузка рекламного модуля и получение его команд с поддомена adc.flyermobi.com.'
)


def parse_original(text: str) -> list[dict[str, str]]:
    headings = list(_ORIGINAL_HEADING.finditer(text))
    if len(headings) != 1:
        raise ValueError('Original BADBOX PDF: expected one C2 Servers table with Domain / Operation')

    records = {}
    for line in text[headings[0].end():].splitlines():
        cells = line.split()
        if not cells:
            break
        if len(cells) != 2 or cells[1] not in {'BADBOX', 'PEACHPIT'}:
            raise ValueError(f'Original BADBOX PDF: unexpected C2 Servers row {line.strip()!r}')
        value, operation = cells
        host = value.lower().replace('[.]', '.')
        if len(host) > 253 or not _HOST.fullmatch(host) or host in records:
            raise ValueError(f'Original BADBOX PDF: invalid or repeated domain {host!r}')

        row = {'indicator': host, 'kind': 'domain', 'match': 'full', 'role': 'C2'}
        if operation == 'PEACHPIT':
            if host != 'flyermobi.com':
                raise ValueError(f'Original BADBOX PDF: review the BADBOX attribution of {host!r}')
            row.update(match='domain', role='C2 рекламного модуля PEACHPIT', scope_evidence=_PEACHPIT_SCOPE)
        else:
            row['role'] = _ORIGINAL_ROLES.get(host, 'C2')
        records[host] = row

    if not records:
        raise ValueError('Original BADBOX PDF: no C2 records found')
    return [records[host] for host in sorted(records)]


def parse_h5(text: str) -> list[dict[str, str]]:
    root_zones = {
        line.lower()
        for line in _ROOT_ZONES.read_text(encoding='utf-8').splitlines()
        if line and not line.startswith('#')
    }
    reader = csv.reader(io.StringIO(text.removeprefix('\ufeff')), strict=True)
    hosts = set()
    try:
        if next(reader, None) != ['Domain']:
            raise ValueError('H5 CSV: expected exactly one column named Domain')
        for row in reader:
            if len(row) != 1:
                raise ValueError(f'H5 CSV line {reader.line_num}: expected one hostname')
            host = row[0].strip().lower().replace('[.]', '.').removesuffix('.')
            if host in _KNOWN_NON_DNS:
                continue
            if (
                len(host) > 253
                or not _HOST.fullmatch(host)
                or host.rsplit('.', 1)[-1] not in root_zones
            ):
                raise ValueError(f'H5 CSV line {reader.line_num}: unexpected DNS name {host!r}')
            hosts.add(host)
    except csv.Error as error:
        raise ValueError(f'H5 CSV line {reader.line_num}: {error}') from error
    if not hosts:
        raise ValueError('H5 CSV: no DNS names found')

    return [
        {'indicator': host, 'kind': 'domain', 'match': 'full', 'role': H5_ROLE}
        for host in sorted(hosts)
    ]
