#!/usr/bin/env python3

import argparse
import json
import os

from .util import (
    re_delivery,
    re_message,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rawdir')
    args = parser.parse_args()

    basedir = os.path.abspath(args.rawdir)

    messages = {}

    dname = os.path.join(basedir, 'mx')
    for fname in os.listdir(dname):
        if not fname.endswith('.json'):
            continue

        with open(os.path.join(dname, fname), 'r') as f:
            raw = json.load(f)
            for pid, obj in raw.items():
                mids = set()
                srcobj = obj
                if 'parent' in obj:
                    srcobj = raw[obj['parent']]

                cksum = srcobj['checksum']
                if cksum not in messages:
                    messages[cksum] = {
                        'pids': {},
                        'subject': srcobj['subject'],
                        'from': srcobj['from'],
                        'mx': {},
                        'egress': {},
                        'mids': [],
                    }
                messages[cksum]['mx'][pid] = obj
                obj.pop('checksum', None)
                obj.pop('subject', None)
                obj.pop('from', None)

                for line in obj['lines']:
                    m = re_delivery.match(line)
                    if m:
                        mids.add(m.group('mid'))

                mids.update(messages[cksum]['mids'])
                messages[cksum]['mids'] = list(mids)

    dname = os.path.join(basedir, 'egress')
    for fname in os.listdir(dname):
        if not fname.endswith('.json'):
            continue

        with open(os.path.join(dname, fname), 'r') as f:
            raw = json.load(f)

        for pid, obj in raw.items():
            mids = []
            for line in obj['lines']:
                m = re_message.match(line)
                if m:
                    mids.append(m.group('env_id'))

            for cksum, mobj in messages.items():
                if not set(mids).isdisjoint(set(mobj['mids'])):
                    mobj['egress'][pid] = obj

    print(json.dumps(messages, indent=2))


if __name__ == '__main__':
    main()
