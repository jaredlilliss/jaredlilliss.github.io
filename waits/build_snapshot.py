#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_snapshot.py -- regenerate The Tally's no-scripting snapshot from the collector's file.

    python waits/build_snapshot.py            (from the repo root; reads queue-board/ed.json)

waits/index.html carries a table that stands in when scripting is off or the collector's
file cannot be read. It was hand-embedded when the page was built (readings to Fri 4 Sep
09:00 AEST) and never refreshed, so a no-JS visitor read a fortnight-old day as the page's
own. This script rewrites exactly four things from ed.json and nothing else: the table's
<tbody>, its <caption>, the rail's build-time aria-valuetext and the kicker's "Readings to"
stamp (all four are what the page's script overwrites when it runs). The arithmetic mirrors the
page's own script line for line -- departments north to south by latitude, the district's
short form, the last reading, the day's busiest reading with its wall-clock quarter-hour
(the published local time, never the machine's zone) -- so the two views agree.

Every other byte of index.html is asserted unchanged before the file is replaced."""
import html, io, json, os, re, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGE = os.path.join(HERE, 'index.html')
DATA = os.path.join(ROOT, 'queue-board', 'ed.json')
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


def main():
    e = json.load(io.open(DATA, encoding='utf-8'))
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
    caption = ('<caption>Snapshot embedded when this page was built &mdash; readings to %s. '
               'With scripting on, the page reads the collector&rsquo;s current file instead.</caption>' % stamp)

    s = io.open(PAGE, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'   # git autocrlf may hand us CRLF; write rows in the file's own ending
    parts = [
        (re.compile(r'<caption>Snapshot embedded when this page was built.*?</caption>', re.S), caption),
        (re.compile(r'(<div class="snap" id="snap">.*?<tbody>\r?\n).*?(\r?\n[ \t]*</tbody>)', re.S), None),
        (re.compile(r'(aria-valuetext=")[^"]*(")'), None),
    ]
    parts.append((re.compile(r'(<span[^>]*\bid="when"[^>]*>)Readings to [^<]*(</span>)'), None))   # the kicker's build-time stamp, replaced by the script when it runs
    out = s
    n1 = len(parts[0][0].findall(out)); out = parts[0][0].sub(caption, out)
    n2 = len(parts[1][0].findall(out)); out = parts[1][0].sub(lambda m: m.group(1) + nl.join(rows) + m.group(2), out)
    n3 = len(parts[2][0].findall(out)); out = parts[2][0].sub(lambda m: m.group(1) + stamp + m.group(2), out)
    n4 = len(parts[3][0].findall(out)); out = parts[3][0].sub(lambda m: m.group(1) + 'Readings to ' + stamp + m.group(2), out)
    if (n1, n2, n3, n4) != (1, 1, 1, 1):
        sys.exit('expected exactly one caption, one tbody, one aria-valuetext and one kicker stamp; found %d, %d, %d, %d - not rebuilt' % (n1, n2, n3, n4))
    # everything outside the four regions must be byte-identical
    blank = lambda t: parts[3][0].sub('', parts[2][0].sub('', parts[1][0].sub('', parts[0][0].sub('', t))))
    if blank(s) != blank(out):
        sys.exit('a byte outside the three regions would change - not rebuilt')
    io.open(PAGE + '.tmp', 'w', encoding='utf-8', newline='').write(out)
    os.replace(PAGE + '.tmp', PAGE)
    print('snapshot rebuilt: %d departments, readings to %s (%d quarter-hours)' % (len(rows), stamp, N))


if __name__ == '__main__':
    main()
