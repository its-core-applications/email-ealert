#!/usr/bin/env python3

import re


# This one might need tweaking in the future
re_from = re.compile(r'.+: Receive \[(?P<ip>[\.0-9]+)\] (?P<hostname>.+\.mailgun\.net):.+RFC5322.From: (?P<addr>(?:dpss-safety-security|UMEmergency|umdearborn-emermgt)@umich.edu)')

re_pid = re.compile(r'(?P<ts>.+) .+\.umich\.edu simta\[(?P<pid>[\.0-9]+)\]:')
re_stale = re.compile(r'.+: Child: .+ (?:process|runner) (?P<child_pid>[\.0-9]+) .+ exited 0')
re_cksum = re.compile(r'.+: Message checksums: [0-9a-z]+ (?P<cksum>[0-9a-z]+)')
re_subj = re.compile(r'.+: Subject: (?P<subj>.+)')
re_child = re.compile(r'.+: Child: launched queue runner (?P<child_pid>[\.0-9]+)')

re_message = re.compile(r'.+: Receive .+ env <(?P<env_id>.+)>: Message Accepted: MID <(?P<mid>.+)> From <(?P<from>.+)>: .+')
re_delivery = re.compile(r'.+: Deliver.SMTP env <(?P<env_id>.+)>: Message Accepted \[(?P<ip>[\.0-9]+)\] (?P<hostname>[-\.a-z]+): transmitted (?P<size>[0-9]+)/[0-9]+: 250 Accepted: \((?P<mid>.+)\)')

re_accepted = re.compile(r'.+: Receive.+: To.+: Accepted$')
re_baduser = re.compile(r'.+: Receive.+: Failed: User not local$')

re_queue = re.compile(r'.+: Queue (?P<domain>.+): Delivery complete: (?P<time>[0-9]+) milliseconds, (?P<msgs>[0-9]+) messages: (?P<msg_a>[0-9]+) A (?P<msg_f>[0-9]+) F (?P<msg_t>[0-9]+) T, (?P<rcpts>[0-9]+) rcpts (?P<rcpt_a>[0-9]+) A (?P<rcpt_f>[0-9]+) F (?P<rcpt_t>[0-9]+) T')
