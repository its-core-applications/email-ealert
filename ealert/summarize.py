#!/usr/bin/env python3

import argparse
import itertools
import json
import os

from datetime import datetime

from .util import (
    re_accepted,
    re_baduser,
    re_message,
    re_queue,
    wrap_zstd,
)


def incr_stat(stats, statname, amount=1):
    if statname not in stats:
        stats[statname] = 0
    stats[statname] += amount


def merge_stats(s1, s2):
    for k, v in s2.items():
        if k not in s1:
            s1[k] = v
        else:
            if type(v) == int:
                s1[k] += v

            elif type(v) == dict:
                merge_stats(s1[k], s2[k])

            elif k.endswith('start'):
                s1[k] = min(s1[k], v)

            elif k.endswith('end'):
                s1[k] = max(s1[k], v)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('jsondir')
    parser.add_argument(
        '--min-gap',
        action='store',
        type=int,
        default=600,
        help='number of seconds before we treat a message with the same subject as belonging to a new alert',
    )
    parser.add_argument('-r', '--raw', action='store_true')
    args = parser.parse_args()

    basedir = os.path.abspath(args.jsondir)

    messages = {}

    for fname in os.listdir(basedir):
        if not fname.endswith('.json') and not fname.endswith('.json.zst'):
            continue

        with open(os.path.join(basedir, fname), 'rb') as f:
            f = wrap_zstd(f, fname)
            raw = json.load(f)
            for cksum, obj in raw.items():
                if cksum not in messages:
                    messages[cksum] = {
                        'ips': {},
                        'receive_histogram': {},
                        'deliver_histogram': {},
                        'domains': {},
                    }
                stats = messages[cksum]
                stats['subject'] = obj['subject']
                stats['from'] = obj['from']
                incr_stat(stats, 'receive_procs', len(obj['mx']))
                incr_stat(stats, 'deliver_procs', len(obj['egress']))

                # Receive stats
                for pid, cobj in obj['mx'].items():
                    if 'ip' in cobj:
                        incr_stat(stats['ips'], cobj['ip'])
                    startts = cobj['lines'][0][:32]
                    endts = cobj['lines'][-1][:32]
                    if startts < stats.get('receive_start', 'A'):
                        stats['receive_start'] = startts
                    if endts > stats.get('receive_end', '0'):
                        stats['receive_end'] = endts

                    rcpts = 0
                    for line in cobj['lines']:
                        if re_accepted.match(line):
                            incr_stat(stats, 'receive_recipients')
                            rcpts += 1
                        elif re_baduser.match(line):
                            incr_stat(stats, 'receive_badusers')
                        elif re_message.match(line):
                            incr_stat(stats['receive_histogram'], line[11:16], rcpts)
                            rcpts = 0
                            incr_stat(stats, 'receive_messages')

                # Delivery stats
                for pid, cobj in obj['egress'].items():
                    startts = cobj['lines'][0][:32]
                    if startts < stats.get('deliver_start', 'A'):
                        stats['deliver_start'] = startts

                    for line in cobj['lines']:
                        m = re_queue.match(line)
                        if m:
                            endts = line[:32]
                            if (m['msg_a'] != '0') and (endts > stats.get('deliver_end', '0')):
                                stats['deliver_end'] = endts
                            if m['domain'] not in stats['domains']:
                                stats['domains'][m['domain']] = {
                                    'start': startts,
                                    'end': endts,
                                    'histogram': {},
                                }
                            dstats = stats['domains'][m['domain']]
                            if startts < dstats['start']:
                                dstats['start'] = startts
                            if endts > dstats['end']:
                                dstats['end'] = endts

                            incr_stat(stats['deliver_histogram'], endts[11:16], int(m['rcpt_a']))
                            incr_stat(stats, 'deliver_recipients', int(m['rcpt_a']))
                            incr_stat(dstats, 'msgs', int(m['msg_a']))
                            incr_stat(dstats, 'rcpts', int(m['rcpt_a']))
                            incr_stat(dstats['histogram'], endts[11:16], int(m['rcpt_a']))
                            incr_stat(dstats, 'time', int(m['time']))

    # Merge overlapping alerts with the same subject
    changed = True
    while changed:
        changed = False
        for cksum1 in list(messages.keys()):
            obj1 = messages.get(cksum1)
            if not obj1:
                # already merged
                continue

            for cksum2, obj2 in list(messages.items()):
                if (obj1 == obj2) or (obj1['subject'] != obj2['subject']):
                    continue

                start1 = datetime.fromisoformat(obj1['receive_start'])
                start2 = datetime.fromisoformat(obj2['receive_start'])
                end1 = datetime.fromisoformat(obj1['receive_end'])
                end2 = datetime.fromisoformat(obj2['receive_end'])

                merge = False
                if (start1 <= start2 <= end1) or (start2 <= start1 <= end2):
                    # start falls within the range
                    merge = True
                elif (start1 <= end2 <= end1) or (start2 <= end1 <= end2):
                    # end falls within the range
                    merge = True

                for ts_pair in itertools.product([start1, end1], [start2, end2]):
                    if abs(ts_pair[0] - ts_pair[1]).total_seconds() < args.min_gap:
                        # close enough
                        merge = True

                if merge:
                    changed = True
                    merge_stats(obj1, obj2)
                    messages.pop(cksum2)

    # Pretty output
    for cksum, obj in sorted(messages.items(), key=lambda x: x[1]['receive_recipients']):
        print(f'Subject: {obj["subject"]}')
        print(f'Start: {obj["receive_start"][:19]}')
        print(f'Receipt End: {obj["receive_end"][:19]}')
        print(f'Delivery End: {obj["deliver_end"][:19]}')
        print(f'Accepted: {obj["receive_recipients"]}')
        print(f'Delivered: {obj["deliver_recipients"]}')
        print(f'Bad Addresses: {obj.get("receive_badusers", 0)}')
        print('')
        print('Received messages per minute:')
        for ts, count in sorted(obj['receive_histogram'].items(), key=lambda x: x[0]):
            print(f'    {ts}: {count}')
        print('')
        print('Delivered messages per minute:')
        for ts, count in sorted(obj['deliver_histogram'].items(), key=lambda x: x[0]):
            print(f'    {ts}: {count}')
        print('')
        print('Domains with >50 recipients:')
        print('')
        for dname, dstats in sorted(obj['domains'].items(), reverse=True, key=lambda x: x[1]['rcpts']):
            if dstats['msgs'] > 0:
                dstats['time_avg_msg'] = dstats['time'] / dstats['msgs']
                dstats['time_avg_rcpt'] = dstats['time'] / (dstats['rcpts'] or 1)
            if dstats['rcpts'] > 50:
                print(dname + ':')
                print(f'    Total: {dstats["rcpts"]}')
                print(f'    Average time per transaction: {dstats["time_avg_msg"] / 1000:.2f} seconds')
                print(f'    Average time per recipient: {dstats["time_avg_rcpt"] / 1000:.2f} seconds')
                print('    Per minute:')
                for ts, count in sorted(dstats['histogram'].items(), key=lambda x: x[0]):
                    print(f'        {ts}: {count}')
                print('')

        if args.raw:
            print(json.dumps(obj, indent=2))


if __name__ == '__main__':
    main()
