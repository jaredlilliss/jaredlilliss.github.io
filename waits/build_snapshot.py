#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_snapshot.py -- regenerate The Tally's no-scripting snapshot from the collector's file.

    python waits/build_snapshot.py                 rebuild from the PUBLISHED ed.json
    python waits/build_snapshot.py --out PATH      write elsewhere, leave index.html alone
    python waits/build_snapshot.py --file PATH     build from a local file (testing only)

waits/index.html carries a table that stands in when scripting is off or the collector's
file cannot be read. It was hand-embedded when the page was built and never refreshed, so a
no-JS visitor read a fortnight-old day as the page's own. This script rewrites exactly four
things and nothing else: the table's <tbody>, its <caption>, the rail's build-time
aria-valuetext and the kicker's stamp (all four are what the page's script overwrites when it
runs). The arithmetic mirrors the page's own script line for line -- departments north to
south by latitude, the district's short form, the last reading, the day's busiest reading
with its wall-clock quarter-hour (the published local time, never the machine's zone) -- so
the two views agree. Every other byte of index.html is asserted unchanged before it is replaced.

⚠️ CORRECTED 19/09/2026, and the bug had been silently shipping stale data to the public page.

    It read ROOT/queue-board/ed.json -- the LOCAL CLONE's copy. But queue-board/refresh.py
    publishes by pushing straight to the GitHub repo through the API (`gh api ... --method
    PUT`); it never writes any local file. So the clone only moves when somebody pulls, and
    this clone was THIRTEEN COMMITS BEHIND. Measured 19/09 14:5x:

        cc\queue-board\ed.json      meta.last 2026-08-27  <- a decoy, 23 days dead
        repo clone  ed.json         meta.last 2026-09-17  <- what this script was reading
        PUBLISHED   ed.json         meta.last 2026-09-19  <- the only real source
        the live page's static text  "Readings to Thu 17 Sep 17:45 AEST"

    Re-running the old script reported "rebuilt ... byte-identical, nothing to do" and that
    was true of its input and false of the world -- the exact shape of a check that cannot
    fire. It now reads the PUBLISHED file over the network and REFUSES TO BUILD if it cannot,
    rather than falling back to a local copy that looks like a source and is not one.
    --file exists only so the known-positive test can feed it a deliberately old source."""
import argparse, html, io, json, os, re, sys, urllib.request
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGE = os.path.join(HERE, 'index.html')
# The published file IS the source of truth, because refresh.py publishes to it directly.
# No local path is a valid default: every one of them can silently go stale.
SOURCE_URL = 'https://jaredlilliss.github.io/queue-board/ed.json'
DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
MONS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def wall_parse(iso):
    m = re.match(r'^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)', iso)
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))


def zone_of(iso):
    m = re.search(r'([+-]\d\d:\d\d)$', iso)
    if not m:
        return ''
    return {'+10:00': 'AEST', '+11:00': 'AEDT'}.get(m.group(1), 'UTC' + m.group(1))


def fmt_t(d):
    return '%02d:%02d' % (d.hour, d.minute)


def fmt_d(d):
    return '%s %d %s' % (DAYS[(d.weekday() + 1) % 7], d.day, MONS[d.month - 1])


def lhd_short(l):
    return l.replace(' Local Health District', ' LHD')


def load_source(path=None):
    """The published file, or an explicit local one for testing. Never a silent fallback."""
    if path:
        sys.stderr.write('source: LOCAL FILE %s (testing only)\n' % path)
        return json.load(io.open(path, encoding='utf-8')), 'local file ' + os.path.basename(path)
    try:
        req = urllib.request.Request(SOURCE_URL, headers={'User-Agent': 'build_snapshot'})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.getcode() != 200:
                sys.exit('source returned HTTP %s - NOT rebuilt' % r.getcode())
            return json.loads(r.read().decode('utf-8')), SOURCE_URL
    except SystemExit:
        raise
    except Exception as ex:
        # Fail closed. A stale local copy is worse than no rebuild, because it looks like one.
        sys.exit('could not read %s (%s) - NOT rebuilt, and no local file was used' % (SOURCE_URL, ex))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--file', help='build from this local ed.json instead (testing only)')
    ap.add_argument('--out', help='write the rebuilt page here instead of index.html')
    args = ap.parse_args()

    e, origin = load_source(args.file)
    F = sorted(e['facilities'], key=lambda f: -f['lat'])
    N = len(F[0]['series'])
    if any(len(f['series']) != N for f in F):
        sys.exit('ragged series - not rebuilt')
    last = wall_parse(F[0]['at'])
    if last is None:
        sys.exit('unreadable time - not rebuilt')
    zone = zone_of(F[0]['at'])
    times = [last - timedelta(minutes=15 * (N - 1 - k)) for k in range(N)]
    rows = []
    for f in F:
        ser = [s or 0 for s in f['series']]
        top = max(ser); k = ser.index(top)
        rows.append('<tr><th scope="row">%s</th><td>%s</td><td>%d</td><td>%d <small>at %s</small></td></tr>' % (
            html.escape(f['name'], quote=True), html.escape(lhd_short(f['lhd']), quote=True), int(f['current'] or 0), top, fmt_t(times[k])))
    stamp = '%s %s %s' % (fmt_d(last), fmt_t(last), zone)

    # ── the snapshot must carry its own age ──────────────────────────────────
    # The page's own rule is "no 'right now' claim on a stale figure". The static
    # kicker used to read "Readings to <time>", which is exactly such a claim: with
    # scripting off it is the only line a visitor sees, and it looks current however
    # old it is. It now says "Snapshot", and when the snapshot is not from today the
    # caption says how old it is in words, so age is visible without reading a date.
    age = (datetime.now().date() - last.date()).days
    if age <= 0:
        old = ''
    elif age == 1:
        old = ' This snapshot is from yesterday.'
    else:
        old = ' This snapshot is %d days old.' % age
    caption = ('<caption>Snapshot embedded when this page was built &mdash; readings to %s.%s '
               'With scripting on, the page reads the collector&rsquo;s current file instead.'
               '</caption>' % (stamp, old))

    s = io.open(PAGE, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'   # git autocrlf may hand us CRLF; write rows in the file's own ending
    parts = [
        (re.compile(r'<caption>Snapshot embedded when this page was built.*?</caption>', re.S), caption),
        (re.compile(r'(<div class="snap" id="snap">.*?<tbody>\r?\n).*?(\r?\n[ \t]*</tbody>)', re.S), None),
        (re.compile(r'(aria-valuetext=")[^"]*(")'), None),
    ]
    # Matches whatever the kicker currently holds, not just the old "Readings to ..." form,
    # so the wording can change without the next run silently failing to find its own region.
    parts.append((re.compile(r'(<span[^>]*\bid="when"[^>]*>).*?(</span>)', re.S), None))
    out = s
    n1 = len(parts[0][0].findall(out)); out = parts[0][0].sub(caption, out)
    n2 = len(parts[1][0].findall(out)); out = parts[1][0].sub(lambda m: m.group(1) + nl.join(rows) + m.group(2), out)
    n3 = len(parts[2][0].findall(out)); out = parts[2][0].sub(lambda m: m.group(1) + stamp + m.group(2), out)
    # "Snapshot", never "Readings to" -- with scripting off this is the only line shown, and
    # "Readings to" reads as current. The page's script replaces it with the live wording.
    n4 = len(parts[3][0].findall(out)); out = parts[3][0].sub(lambda m: m.group(1) + 'Snapshot &mdash; readings to ' + stamp + m.group(2), out)
    if (n1, n2, n3, n4) != (1, 1, 1, 1):
        sys.exit('expected exactly one caption, one tbody, one aria-valuetext and one kicker stamp; found %d, %d, %d, %d - not rebuilt' % (n1, n2, n3, n4))
    # everything outside the four regions must be byte-identical
    blank = lambda t: parts[3][0].sub('', parts[2][0].sub('', parts[1][0].sub('', parts[0][0].sub('', t))))
    if blank(s) != blank(out):
        sys.exit('a byte outside the three regions would change - not rebuilt')
    target = args.out or PAGE
    io.open(target + '.tmp', 'w', encoding='utf-8', newline='').write(out)
    os.replace(target + '.tmp', target)
    print('snapshot rebuilt from %s' % origin)
    print('  %d departments, readings to %s (%d quarter-hours), source age %d day(s)'
          % (len(rows), stamp, N, age))
    print('  written to %s' % target)
    if age > 0:
        print('  NOTE: the page now says so on its face - "%s"' % old.strip())


if __name__ == '__main__':
    main()
