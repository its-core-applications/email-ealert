#!/usr/bin/env python3

import argparse
import io
import json
import re
import sys

import zstandard as zstd

from .util import (
    re_child,
    re_cksum,
    re_from,
    re_message,
    re_pid,
    re_stale,
    re_subj,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-t', '--type',
        default='mx',
    )
    parser.add_argument(
        '-m', '--midlist',
    )
    parser.add_argument('logfile')
    args = parser.parse_args()

    pids = {}
    pid_lines = {}

    mids = []
    if args.type != 'mx':
        if not args.midlist:
            print('Non-MX log parsing requires a MID list so that we know what to look for', file=sys.stderr)
            sys.exit(1)
        with open(args.midlist, 'r') as f:
            mids = json.load(f)

    fname = args.logfile

    with open(fname, 'rb') as f:
        if fname.endswith('.zst'):
            f = zstd.ZstdDecompressor().stream_reader(f)
        ftext = io.TextIOWrapper(f, encoding='utf-8', errors='backslashreplace')
        for line in ftext:
            m = re_pid.match(line)
            if not m:   # Not a simta log line
                continue
            pid = m.group('pid')

            if pid not in pid_lines:
                pid_lines[pid] = []

            pid_lines[pid].append(line)

            m = re_stale.match(line)
            if m:
                pid_lines.pop(m.group('child_pid'), None)
                continue

            if pid not in pids:
                # Check to see if this is a PID we should start tracking
                if args.type == 'mx':
                    m = re_from.match(line)
                    if m:
                        pids[pid] = {
                            'from': m.group('addr'),
                            'ip': m.group('ip'),
                            'host': m.group('hostname'),
                            'lines': pid_lines[pid],
                        }
                else:
                    m = re_message.match(line)
                    if m and m.group('env_id') in mids:
                        pids[pid] = {
                            'lines': pid_lines[pid],
                        }
                # If it's not, it's not an interesting line
                continue

            # Capture children of tracked PIDs
            m = re_child.match(line)
            if m:
                pids[m.group('child_pid')] = {
                    'parent': pid,
                    'lines': pid_lines[pid],
                }
                continue

            # Next, check for some receipt metadata we want to track
            if args.type == 'mx':
                if 'parent' not in pids[pid]:
                    m = re_cksum.match(line)
                    if m:
                        pids[pid]['checksum'] = m.group('cksum')
                        continue

                    m = re_subj.match(line)
                    if m:
                        pids[pid]['subject'] = m.group('subj')
                        continue

    print(json.dumps(pids, indent=2))


if __name__ == '__main__':
    main()