"""Build the DAT files and validate a candidate before replacing dist files."""

import argparse
import datetime as dt
import hashlib
import ipaddress
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from feed_badbox12 import H5_SOURCE
from geodata import (
    DATA, DIST, ROOT, MATCH_TYPES, SHARED, encode, excluded, field, json_text,
    load_exclusions, load_records, normalize, read_category, read_json,
)

FILES = ('badbox.dat', 'badbox-ip.dat')
H5_FILE = 'badbox-h5.dat'
XRAY_VERSION = '26.11.9'


def domain_rules(records):
    domains = {}
    for row in records:
        if row['kind'] == 'domain':
            host = row['indicator']
            mode = MATCH_TYPES[row['match']]
            domains[host] = min(domains.get(host, mode), mode)
    return sorted(domains.items())


def rules_for(records):
    domains = domain_rules(records)
    networks = {ipaddress.ip_network(row['indicator']) for row in records
                if row['kind'] == 'ip' and 'port' not in row}
    if not domains or not networks:
        raise ValueError('Both BADBOX categories must contain at least one rule')
    return domains, sorted(networks, key=lambda n: (n.version, int(n.network_address), n.prefixlen))


def port_rules_for(records):
    addresses = {}
    for row in records:
        if 'port' in row:
            addresses.setdefault(row['port'], set()).add(row['indicator'])
    return [{'ip': sorted(networks), 'port': port} for port, networks in sorted(addresses.items())]


def write_domains(path, domains):
    path.write_bytes(encode(
        field(1, mode) + field(2, host.encode('ascii')) for host, mode in domains
    ))


def compile_files(directory, domains, networks):
    write_domains(directory / FILES[0], domains)
    directory.joinpath(FILES[1]).write_bytes(encode(
        field(1, network.network_address.packed) + field(2, network.prefixlen)
        for network in networks
    ))


def decode_domains(path):
    domains = []
    for rule in read_category(path.read_bytes()):
        (type_field, mode), (value_field, value) = rule
        if type_field != 1 or mode not in MATCH_TYPES.values() or value_field != 2:
            raise ValueError(f'Invalid GeoSite rule: {rule!r}')
        domains.append((value.decode('ascii'), mode))
    return domains


def decode_files(directory):
    domains = decode_domains(directory / FILES[0])
    networks = []
    for rule in read_category(directory.joinpath(FILES[1]).read_bytes()):
        (address_field, address), (prefix_field, prefix) = rule
        if address_field != 1 or prefix_field != 2:
            raise ValueError(f'Invalid GeoIP rule: {rule!r}')
        networks.append(ipaddress.ip_network((ipaddress.ip_address(address), prefix), strict=True))
    return domains, networks


def matches_domain(value, domains):
    return any(value == host or (mode == 2 and value.endswith('.' + host)) for host, mode in domains)


def matches_ip(address, networks):
    return any(address in net for net in networks)


def check_coverage(records, domains, networks, probes, port_rules=()):
    endpoints = {(network, rule['port']) for rule in port_rules for network in rule['ip']}
    checks = {}
    for row in records:
        value = row['indicator']
        if row['kind'] == 'domain':
            covered = matches_domain(value, domains)
        elif 'port' in row:
            covered = (value, row['port']) in endpoints
        else:
            covered = ipaddress.ip_network(value) in networks
        if not covered:
            raise ValueError(f'Routing rules do not cover {value} from {row["source"]}')
        source = checks.setdefault(row['source'], {'domain_rows': 0, 'ip_rows': 0, 'covered_rows': 0, 'variants': []})
        source[row['kind'] + '_rows'] += 1
        source['covered_rows'] += 1
        if row['variant'] not in source['variants']:
            source['variants'].append(row['variant'])

    for host, mode in domains:
        children = 'badbox-geodata-probe.' + host
        expected = mode == 2 or any(
            host.endswith('.' + parent) for parent, parent_mode in domains if parent_mode == 2
        )
        if matches_domain(children, domains) != expected:
            raise ValueError(f'Unexpected subdomain scope: {host}')

    for platform in SHARED:
        for sample in (platform, 'badbox-geodata-unlisted.' + platform):
            if matches_domain(sample, domains):
                raise ValueError(f'Shared platform unexpectedly covered: {sample}')

    for network in networks:
        for adjacent in (int(network.network_address) - 1, int(network.broadcast_address) + 1):
            if 0 <= adjacent < 2 ** network.max_prefixlen:
                sample = type(network.network_address)(adjacent)
                covered = any(
                    row['kind'] == 'ip' and 'port' not in row and sample in ipaddress.ip_network(row['indicator'])
                    for row in records
                )
                if matches_ip(sample, networks) != covered:
                    raise ValueError(f'Unexpected IP coverage at {sample}')

    results = []
    for probe in probes:
        if probe['kind'] == 'domain':
            actual = matches_domain(normalize(probe['indicator'], 'domain'), domains)
        elif probe['kind'] == 'ip':
            address = ipaddress.ip_address(probe['indicator'])
            network = f'{address}/{address.max_prefixlen}'
            actual = matches_ip(address, networks) or (network, probe.get('port')) in endpoints
        else:
            raise ValueError(f'Unknown probe kind: {probe!r}')
        if actual != probe['blocked']:
            raise ValueError(f'Unexpected routing coverage at {probe["indicator"]}: {actual}')
        results.append(dict(probe, passed=True))
    return {'category': 'BADBOX', 'source_rows': checks, 'probes': results,
            'domain_scopes_checked': len(domains), 'ip_scopes_checked': len(networks),
            'port_scopes_checked': len(endpoints)}


def test_xray(executable, directory, port_rules):
    version = subprocess.run([executable, 'version'], check=True, text=True, capture_output=True).stdout.split()
    if version[:2] != ['Xray', XRAY_VERSION]:
        raise ValueError(f'Expected Xray {XRAY_VERSION}, got {" ".join(version[:2])}')
    rules = read_json(ROOT / 'snippets' / 'BADBOX-RULES.json')
    expected = [
        {'domain': ['ext:badbox.dat:badbox']},
        {'ip': ['ext:badbox-ip.dat:badbox']},
        *port_rules,
    ]
    if rules != [dict(rule, type='field', outboundTag='BLOCK') for rule in expected]:
        raise ValueError('BADBOX-RULES does not match the GeoSite, GeoIP and port-specific evidence')
    snippet, = read_json(ROOT / 'snippets' / 'GEODATA.json')
    geodata = snippet['geodata']
    assets = geodata['assets']
    if (geodata['cron'] != '30 2 * * 1' or 'outbound' in geodata
            or {entry['file'] for entry in assets} != {*FILES, 'security.dat', 'security-ip.dat'}
            or len(assets) != 4):
        raise ValueError('GEODATA must include both BADBOX and both Chocolate4U assets')
    config = directory / 'xray-test.json'
    h5_rule = {'type': 'field', 'domain': [f'ext:{H5_FILE}:badbox'], 'outboundTag': 'BLOCK'}
    config.write_text(json_text({
        'geodata': dict(geodata, assets=[entry for entry in assets if entry['file'] in FILES]),
        'outbounds': [{'tag': 'BLOCK', 'protocol': 'blackhole'}],
        'routing': {'domainStrategy': 'AsIs', 'rules': [*rules, h5_rule]},
    }), encoding='utf-8')
    env = dict(os.environ)
    env.pop('xray.location.asset', None)
    env['XRAY_LOCATION_ASSET'] = str(directory)
    subprocess.run([executable, 'run', '-test', '-config', str(config)], env=env, check=True, timeout=30)
    config.unlink()


def check_history(records, exclusions, previous):
    if previous is None:
        return
    current = {(row['source'], row['kind'], row['indicator']) for row in records}
    for source, kind, value in previous['included_evidence']:
        if (source, kind, value) not in current and not excluded(exclusions, kind, value, source):
            raise ValueError(f'Previously published indicator {value} from {source} was removed without a source-specific exclusion')


def publish_local(xray, output, baseline):
    records = load_records()
    exclusions = load_exclusions()
    if any(excluded(exclusions, row['kind'], row['indicator'], row['source']) for row in records):
        raise ValueError('An indicator is both included and excluded by the same source')
    previous = read_json(baseline) if baseline.is_file() else None
    check_history(records, exclusions, previous)
    main_records = [row for row in records if row['source'] != H5_SOURCE]
    h5_records = [row for row in records if row['source'] == H5_SOURCE]
    if not h5_records or any(row['kind'] != 'domain' or row['match'] != 'full' for row in h5_records):
        raise ValueError('The H5 appendix must contain exact domain rules')
    domains, networks = rules_for(main_records)
    h5_domains = domain_rules(h5_records)
    port_rules = port_rules_for(main_records)
    probes = read_json(DATA / 'probes.json')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.candidate-', dir=output) as tmp:
        candidate = Path(tmp)
        compile_files(candidate, domains, networks)
        write_domains(candidate / H5_FILE, h5_domains)
        actual_domains, actual_networks = decode_files(candidate)
        actual_h5 = decode_domains(candidate / H5_FILE)
        if actual_domains != domains or actual_networks != networks or actual_h5 != h5_domains:
            raise ValueError('DAT round-trip differs from normalized source rules')
        coverage = check_coverage(main_records, actual_domains, actual_networks, probes, port_rules)
        h5_coverage = check_coverage(h5_records, actual_h5, [], [])
        test_xray(xray, candidate, port_rules)
        artifacts = {}
        for name, count in zip((*FILES, H5_FILE), (len(domains), len(networks), len(h5_domains))):
            payload = candidate.joinpath(name).read_bytes()
            artifacts[name] = {'records': count, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
        evidence_inputs = sorted(DATA.glob('*.json'))
        evidence_digest = hashlib.sha256(json_text({
            path.name: read_json(path) for path in evidence_inputs
        }).encode('utf-8')).hexdigest()
        report = {
            'schema_version': 2,
            'artifacts': artifacts,
            'xray_config_check': {'version': XRAY_VERSION, 'passed': True},
            'coverage': coverage,
            'h5_coverage': h5_coverage,
            'port_rules': port_rules,
            'included_evidence': sorted([r['source'], r['kind'], r['indicator']] for r in records),
            'exclusions': exclusions,
            'data_sha256': evidence_digest,
        }
        if previous and report == {key: value for key, value in previous.items() if key != 'built_at'}:
            report['built_at'] = previous['built_at']
        else:
            report['built_at'] = dt.datetime.now(dt.UTC).isoformat(timespec='seconds')
        candidate.joinpath('report.json').write_text(json_text(report), encoding='utf-8')
        candidate.joinpath('SHA256SUMS').write_text(''.join(
            f'{artifact["sha256"]}  {name}\n' for name, artifact in artifacts.items()
        ), encoding='utf-8')
        for name in (*artifacts, 'report.json', 'SHA256SUMS'):
            candidate.joinpath(name).replace(output / name)
    for name, artifact in artifacts.items():
        print(f'{name}: {artifact["records"]} rules, {artifact["bytes"]} bytes, SHA-256 {artifact["sha256"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xray', default='xray', help=f'Path to Xray {XRAY_VERSION}')
    parser.add_argument('--output', type=Path, default=DIST)
    parser.add_argument('--baseline', type=Path, default=DIST / 'report.json')
    args = parser.parse_args()
    try:
        publish_local(args.xray, args.output.resolve(), args.baseline.resolve())
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(f'Build rejected: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
