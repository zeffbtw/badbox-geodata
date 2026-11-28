"""Summarize changes between two validated BADBOX DAT versions."""

import argparse
from pathlib import Path

from build import H5_FILE, decode_domains, decode_files
from geodata import read_json


def change_row(label, before, after, changed_scope='—'):
    previous, current = set(before), set(after)
    added = len(current - previous)
    removed = len(previous - current)
    return f'| {label} | {len(previous)} | {len(current)} | {added} | {removed} | {changed_scope} |'


def domain_row(label, previous, current):
    before, after = dict(previous), dict(current)
    changed_scope = sum(before[host] != after[host] for host in before.keys() & after.keys())
    return change_row(label, before, after, changed_scope)


def h5_rules(directory):
    path = directory / H5_FILE
    return decode_domains(path) if path.is_file() else []


def ip_port_pairs(directory):
    path = directory / 'report.json'
    port_rules = read_json(path).get('port_rules', []) if path.is_file() else []
    return {(ip, rule['port']) for rule in port_rules for ip in rule['ip']}


def describe_update(previous, current):
    previous_domains, previous_networks = decode_files(previous)
    current_domains, current_networks = decode_files(current)

    return '\n'.join([
        '| Rules | Before | After | Added | Removed | Match type changed |',
        '| --- | ---: | ---: | ---: | ---: | ---: |',
        domain_row('Domains (`badbox.dat`)', previous_domains, current_domains),
        change_row('IP/CIDR (`badbox-ip.dat`)', previous_networks, current_networks),
        domain_row(f'Optional H5 domains (`{H5_FILE}`)', h5_rules(previous), h5_rules(current)),
        change_row('IP and port pairs (`BADBOX-RULES`)', ip_port_pairs(previous), ip_port_pairs(current)),
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path, help='Directory with the published DAT files')
    parser.add_argument('current', type=Path, help='Directory with the newly built DAT files')
    args = parser.parse_args()
    print(describe_update(args.previous, args.current))


if __name__ == '__main__':
    main()
