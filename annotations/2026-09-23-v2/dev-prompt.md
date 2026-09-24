You are writing a small DEV set for a benchmark of small language models on practical structured tasks. Do not read files or use tools. For each task below, write 10 NEW items that follow the task's guidelines, are unambiguous under those guidelines, and do not copy or paraphrase the example items. Vary difficulty and cover every allowed label value.

Output JSONL only, one object per line, no prose or code fences: {"task": "<task>", "id": "<task-prefix>-dev-NN", "text": "...", "expected": {<every field for that task>}}. Use id prefixes log, ticket, event. Output exactly 30 lines.

## Task: log-triage
Fields: service, severity
Guidelines: You triage single homelab log lines. service is the name of the program that emitted the line exactly as it appears (the syslog tag before [pid] or ':', e.g. 'sshd', 'kernel', 'CRON'; for nginx access or error log format, 'nginx'; for PostgreSQL log format, 'postgres'). severity is one of: info (routine, normal operation), warn (degraded or unusual but still working; worth watching), error (an operation failed; partial breakage), critical (hardware failure, data-loss risk, or a service is down).
Examples (do not reuse):
{"text": "Sep 23 08:14:02 nas01 sshd[2211]: Accepted publickey for alice from 192.0.2.12 port 51234 ssh2: ED25519 SHA256:k3j...", "expected": {"service": "sshd", "severity": "info"}}
{"text": "Sep 23 10:41:02 nas01 kernel: ata3.00: failed command: READ FPDMA QUEUED; ata3: hard resetting link; blk_update_request: I/O error, dev sdc, sector 9812334", "expected": {"service": "kernel", "severity": "critical"}}

## Task: support-tickets
Fields: category, urgent
Guidelines: You route customer support messages. category is one of: billing (charges, invoices, plans, discounts), bug (the product is broken or behaves wrongly), feature-request (asking for new functionality), account-access (login, passwords, 2FA, admins, account changes or security), shipping (physical orders and deliveries). urgent is true only if the customer faces serious harm, data loss, a security compromise, a hard deadline within about a day, or many users blocked from core functionality; otherwise false.
Examples (do not reuse):
{"text": "Your system charged my card $4,800 instead of $48. That is my rent money. Please reverse this TODAY.", "expected": {"category": "billing", "urgent": true}}
{"text": "Would love a keyboard shortcut to archive items. Would save me a lot of clicks.", "expected": {"category": "feature-request", "urgent": false}}

## Task: event-extraction
Fields: date, startTime, durationMinutes
Guidelines: Today is Wednesday, September 23, 2026. Extract the single event mentioned in the message. date is YYYY-MM-DD; relative weekdays ('Friday', 'this Friday', 'next Friday') mean the first such weekday after today. startTime is 24-hour HH:MM; a time without am/pm means the daytime reading (for example 'at 3' is 15:00, 'at 9' is 09:00). durationMinutes is the length in minutes when the message states an end time or a duration, otherwise 0.
Examples (do not reuse):
{"text": "Reminder: quarterly planning is this Friday from 9 to 11am in the big conference room.", "expected": {"date": "2026-09-25", "startTime": "09:00", "durationMinutes": 120}}
{"text": "Webinar: 'Intro to ZFS' on 2026-10-01 at 18:00 UTC, runs 90 minutes.", "expected": {"date": "2026-10-01", "startTime": "18:00", "durationMinutes": 90}}
