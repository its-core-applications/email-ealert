#!/usr/bin/env python3

import argparse
import json
import os

from .util import (
    re_delivery,
    wrap_zstd,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('jsondir')
    args = parser.parse_args()

    dname = os.path.abspath(args.jsondir)

    messages = set()

    for fname in os.listdir(dname):
        if not fname.endswith('.json') and not fname.endswith('.json.zst'):
            continue

        with open(os.path.join(dname, fname), 'r') as f:
            f = wrap_zstd(f, fname)
            raw = json.load(f)
            for pid, obj in raw.items():
                for line in obj['lines']:
                    m = re_delivery.match(line)
                    if m:
                        messages.add(m['mid'])

    print(json.dumps(list(messages), indent=2))


if __name__ == '__main__':
    main()
