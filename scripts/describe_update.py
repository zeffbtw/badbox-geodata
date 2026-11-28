"""Summarize changes between two validated BADBOX DAT versions."""

import argparse
from pathlib import Path

from build import decode_files


def change_row(label, before, after, changed_scope='—'):
    previous, current = set(before), set(after)
    added = len(current - previous)
    removed = len(previous - current)
    return f'| {label} | {len(previous)} | {len(current)} | {added} | {removed} | {changed_scope} |'


def describe_update(previous, current):
    previous_domains, previous_networks = decode_files(previous)
    current_domains, current_networks = decode_files(current)
    before, after = dict(previous_domains), dict(current_domains)
    changed_scope = sum(before[host] != after[host] for host in before.keys() & after.keys())

    return '\n'.join([
        '| Rules | Before | After | Added | Removed | Match type changed |',
        '| --- | ---: | ---: | ---: | ---: | ---: |',
        change_row('Domains (`badbox.dat`)', before, after, changed_scope),
        change_row('IP/CIDR (`badbox-ip.dat`)', previous_networks, current_networks),
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path, help='Directory with the published DAT files')
    parser.add_argument('current', type=Path, help='Directory with the newly built DAT files')
    args = parser.parse_args()
    print(describe_update(args.previous, args.current))


if __name__ == '__main__':
    main()
