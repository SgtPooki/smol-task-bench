You are an independent data annotator for a benchmark. Label every item below from the text and the task guidelines ONLY. Do not read any files, do not use tools, do not search. Another annotator labeled these separately; you have not seen their labels and should not guess them.

For each item output exactly one JSON object on its own line (JSONL), nothing else: no prose, no code fences. Each object has:
- "id"
- the task's fields, using the allowed values/formats from the guidelines (use null for durationMinutes when no duration or end time is stated)
- "ambiguous": true if a careful reader could reasonably pick a different label for any field under these guidelines, else false
- "note": when ambiguous is true, a short reason naming the field and the alternative reading; otherwise ""

Output all 90 lines, in order, then stop.


## Task: log-triage
Fields: service, severity
Guidelines: You triage single homelab log lines. service is the name of the program that emitted the line exactly as it appears (the syslog tag before [pid] or ':', e.g. 'sshd', 'kernel', 'CRON'; for nginx access or error log format, 'nginx'; for PostgreSQL log format, 'postgres'). severity is one of: info (routine, normal operation), warn (degraded or unusual but still working; worth watching), error (an operation failed; partial breakage), critical (hardware failure, data-loss risk, or a service is down).

[log-01] Sep 23 08:14:02 nas01 sshd[2211]: Accepted publickey for russ from 10.0.0.12 port 51234 ssh2: ED25519 SHA256:k3j...
[log-02] Sep 23 08:15:10 pve1 systemd[1]: Started Daily apt download activities.
[log-03] Sep 23 03:00:01 nas01 CRON[8812]: (root) CMD (/usr/local/bin/zfs-auto-snapshot --quiet --label=daily)
[log-04] Sep 23 09:02:44 router dhcpd[912]: DHCPACK on 10.0.0.57 to 3c:22:fb:11:08:9a (livingroom-tv) via br0
[log-05] 10.0.0.12 - - [23/Sep/2026:09:12:01 +0000] "GET /api/health HTTP/1.1" 200 17 "-" "Uptime-Kuma/1.23"
[log-06] 2026-09-23 02:00:03.120 UTC [4410] LOG:  checkpoint complete: wrote 1842 buffers (11.2%); 0 WAL file(s) added, 0 removed, 1 recycled
[log-07] Sep 23 07:30:12 docker01 dockerd[1022]: time="2026-09-23T07:30:12Z" level=info msg="Container 4f2a1c started" image=jellyfin/jellyfin:10.10
[log-08] Sep 23 06:00:00 nas01 smartd[733]: Device: /dev/sda [SAT], SMART Usage Attribute: 194 Temperature_Celsius changed from 34 to 35
[log-09] Sep 23 06:30:00 nas01 smartd[733]: Device: /dev/sdb [SAT], 8 Currently unreadable (pending) sectors
[log-10] Sep 23 11:02:17 pve1 kernel: [88412.221] CPU3: Core temperature above threshold, cpu clock throttled (total events = 41)
[log-11] 2026-09-23 10:41:55.002 UTC [5120] WARNING:  there is already a transaction in progress
[log-12] 2026/09/23 10:12:44 [warn] 311#311: *8812 an upstream response is buffered to a temporary file /var/cache/nginx/proxy_temp/2/00/0000000002 while reading upstream
[log-13] Sep 23 12:01:40 docker01 dockerd[1022]: time="2026-09-23T12:01:40Z" level=warning msg="Health check for container 7bd1e0 failed 1 of 3 times"
[log-14] Sep 23 04:12:09 nas01 netdata[1502]: WARNING: disk space usage for /mnt/tank is 86% (threshold 85%)
[log-15] Sep 23 00:00:04 web01 certbot[3310]: Certificate for home.example.net expires in 9 days; renewal attempt scheduled
[log-16] 2026/09/23 10:14:02 [error] 311#311: *9120 upstream timed out (110: Connection timed out) while reading response header from upstream, client: 10.0.0.7, server: jellyfin.lan, upstream: "http://10.0.0.20:8096/"
[log-17] Sep 23 02:30:01 nas01 CRON[9921]: (russ) MAIL (mailed 212 bytes of output but got status 0x004b from MTA)
[log-18] 2026-09-23 11:20:31.771 UTC [6021] ERROR:  duplicate key value violates unique constraint "users_email_key"
[log-19] Sep 23 07:45:03 docker01 systemd[1]: restic-backup.service: Main process exited, code=exited, status=1/FAILURE
[log-20] Sep 23 13:10:02 docker01 dockerd[1022]: time="2026-09-23T13:10:02Z" level=error msg="Handler for POST /v1.45/containers/create returned error: pull access denied for ghcr.io/acme/private-app"
[log-21] Sep 23 14:22:10 nas01 sshd[3312]: error: Could not load host key: /etc/ssh/ssh_host_ed25519_key
[log-22] Sep 23 01:05:44 nas01 rsync[7710]: rsync error: some files/attrs were not transferred (see previous errors) (code 23) at main.c(1338)
[log-23] Sep 23 10:41:02 nas01 kernel: ata3.00: failed command: READ FPDMA QUEUED; ata3: hard resetting link; blk_update_request: I/O error, dev sdc, sector 9812334
[log-24] Sep 23 10:44:19 nas01 zed[1502]: eid=230 class=statechange pool='tank' vdev=sdc state=FAULTED; pool tank is DEGRADED
[log-25] Sep 23 15:01:55 docker01 kernel: Out of memory: Killed process 22114 (postgres) total-vm:8123344kB, anon-rss:6021220kB
[log-26] 2026-09-23 15:02:01.004 UTC [1] PANIC:  could not write to file "pg_wal/xlogtemp.1": No space left on device
[log-27] Sep 23 15:03:12 pve1 systemd[1]: pve-cluster.service: Failed with result 'exit-code'; start request repeated too quickly, giving up
[log-28] Sep 23 18:20:44 nas01 apcupsd[611]: Power failure. Running on UPS batteries, 4 minutes remaining; initiating shutdown
[log-29] Sep 23 19:02:10 pve1 kernel: EXT4-fs error (device nvme0n1p2): ext4_journal_check_start:83: Detected aborted journal; remounting filesystem read-only
[log-30] Sep 23 06:31:00 nas01 smartd[733]: Device: /dev/sdd [SAT], FAILED SMART self-check. BACK UP DATA NOW!

## Task: support-tickets
Fields: category, urgent
Guidelines: You route customer support messages. category is one of: billing (charges, invoices, plans, discounts), bug (the product is broken or behaves wrongly), feature-request (asking for new functionality), account-access (login, passwords, 2FA, admins, account changes or security), shipping (physical orders and deliveries). urgent is true only if the customer faces serious harm, data loss, a security compromise, or a hard deadline within about a day; otherwise false.

[ticket-01] Hi, I was charged twice for my March subscription. Can you refund the duplicate charge when you get a chance?
[ticket-02] Can I get an invoice with our company VAT number on it? Accounting needs it for last quarter.
[ticket-03] Your system charged my card $4,800 instead of $48. That is my rent money. Please reverse this TODAY.
[ticket-04] How do I switch from monthly to annual billing? I'd like the discount.
[ticket-05] Is there a student discount? I just started at university.
[ticket-06] Our payment failed and the dashboard says the account will be suspended in 2 hours. We have a launch tonight, please help.
[ticket-07] The dark mode toggle doesn't remember my setting after I log out. Minor, just FYI.
[ticket-08] Since this morning's update none of our users can save documents — every save throws 'Error 500'. Our whole team is blocked.
[ticket-09] Typo on the pricing page: 'Proffesional' should be 'Professional'.
[ticket-10] CSV export puts the date column in the wrong timezone. Workaround is fine for now.
[ticket-11] Data is being deleted! When two people edit the same record, one person's changes vanish completely. We've lost a day of work.
[ticket-12] The mobile app crashes when I rotate the screen on the settings page. Android 15, Pixel 8.
[ticket-13] Would love a keyboard shortcut to archive items. Would save me a lot of clicks.
[ticket-14] Any plans to support SSO with Okta? It would help us roll this out company-wide next year.
[ticket-15] Could you add a way to export reports as PDF?
[ticket-16] Please add Webhooks for when a task is completed so we can hook it into Slack.
[ticket-17] It would be nice if the calendar view could start the week on Monday.
[ticket-18] Suggestion: let us pin favorite projects to the top of the sidebar.
[ticket-19] I changed my email address and now I'm not sure which one to log in with. Can you check?
[ticket-20] I'm locked out and our payroll runs in one hour — I'm the only admin. The 2FA codes aren't arriving.
[ticket-21] How do I add a second admin to our workspace?
[ticket-22] Someone changed my password and email without my permission. I think my account was hacked, please lock it now.
[ticket-23] The password reset email went to spam, but it worked. Maybe look at your email settings?
[ticket-24] Can you delete my old account under my personal email? I only use the work one now.
[ticket-25] My order #10442 says shipped but tracking hasn't updated in 3 days. Any news?
[ticket-26] Can I change the delivery address on an order I placed an hour ago?
[ticket-27] The replacement insulin cooler I ordered hasn't arrived and my medication will spoil tomorrow. Where is it?
[ticket-28] Do you ship to Canada? I didn't see it in the country list.
[ticket-29] Package arrived with a dented box but the item inside seems fine. Just letting you know.
[ticket-30] Wrong item delivered for our wedding tomorrow — we got 12 chairs instead of 120. We need the rest urgently.

## Task: event-extraction
Fields: date, startTime, durationMinutes
Guidelines: Today is Wednesday, September 23, 2026. Extract the single event mentioned in the message. date is YYYY-MM-DD; relative weekdays ('Friday', 'this Friday', 'next Friday') mean the first such weekday after today. startTime is 24-hour HH:MM. durationMinutes is the length in minutes if the message states an end time or duration, otherwise omit it.

[event-01] Dentist appointment confirmed for October 6, 2026 at 2:30 PM. Please arrive 10 minutes early.
[event-02] Hey! Lunch tomorrow at noon at the Thai place on 5th?
[event-03] Reminder: quarterly planning is this Friday from 9 to 11am in the big conference room.
[event-04] Can we move our 1:1 to next Tuesday at 3pm? Same Zoom link, 30 min.
[event-05] Your flight UA 1432 departs Nov 2 at 07:15 from SFO.
[event-06] Book club meets Sunday at 4 — bring snacks! We usually go about two hours.
[event-07] The plumber will come by on Monday between 8 and 10 in the morning.
[event-08] Team offsite: October 15th, 9:30am–4:30pm, Riverside Hall.
[event-09] Pickup for the kids' soccer practice is at 5:45pm today.
[event-10] Webinar: 'Intro to ZFS' on 2026-10-01 at 18:00 UTC, runs 90 minutes.
[event-11] Let's do the code review Thursday at 10:15, should take 45 minutes max.
[event-12] Parent-teacher conference scheduled for 10/08 at 6:30 PM (15-minute slot).
[event-13] Can you make a call the day after tomorrow at 11? Only need 20 min.
[event-14] Oil change booked for Saturday, 8 AM sharp.
[event-15] Your vaccination appointment: Tue 13 Oct 2026, 09:40.
[event-16] Standup is moved to 9:05 starting next Monday.
[event-17] Concert tickets: December 12, doors 7pm, show at 8pm.
[event-18] Movie night next Friday at 7:30pm, a 3 hour epic so plan accordingly.
[event-19] Interview with Acme Corp on Oct 20 at 1pm Pacific; it's a 1-hour panel.
[event-20] Garbage pickup changed to Thursdays at 6am.
[event-21] Yoga class tonight 8:15–9:00pm.
[event-22] Vet checkup for Luna on September 30 at 4:20pm.
[event-23] Board meeting Monday 28 September, 14:00–15:30 CET.
[event-24] Haircut next Wednesday at half past ten in the morning.
[event-25] The furnace inspection is at 1 o'clock on the 2nd of October, about an hour.
[event-26] Hackathon kicks off on Friday October 9 at 6pm and runs 24 hours.
[event-27] Pay the property tax by Nov 30 — portal closes at 5pm.
[event-28] Coffee with Sam in two weeks, same time as today: 8:45am.
[event-29] Election day is Tuesday, November 3, 2026; polls open at 7 AM.
[event-30] Family dinner at mom's this Saturday at 6:30 in the evening.
