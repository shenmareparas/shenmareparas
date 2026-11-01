#!/usr/bin/env python3
"""Generate self-contained profile SVGs using only Python's standard library.

Inspired by Aman Sanoj's .github architecture (amansanoj/.github).
python3 scripts/build_profile.py --fetch   # fresh public GitHub data
python3 scripts/build_profile.py          # render the committed snapshot offline
"""
import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USER = 'shenmareparas'
THEMES = {
    'dark': dict(
        bg='#050505', fg='#f1f5f9', muted='#71717a', line='#27272a',
        panel='#09090b', blue='#38bdf8', accent='#0ea5e9', gold='#fbbf24',
        ramp=['#161b22', '#075985', '#0284c7', '#38bdf8', '#bae6fd'],
    ),
    'light': dict(
        bg='#fafafa', fg='#18181b', muted='#71717a', line='#e4e4e7',
        panel='#f4f4f5', blue='#0284c7', accent='#0369a1', gold='#d97706',
        ramp=['#e8eaee', '#bae6fd', '#38bdf8', '#0284c7', '#0369a1'],
    ),
}


# ---------------------------------------------------------------- data

class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.tips = {}
        self.tip_id = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'data-date' in a and 'data-level' in a:
            cell_id = a.get('id', a['data-date'])
            self.cells[cell_id] = {'date': a['data-date'], 'level': int(a['data-level'])}
        if tag == 'tool-tip':
            self.tip_id = a.get('for')
            if self.tip_id:
                self.tips[self.tip_id] = ''

    def handle_data(self, data):
        if self.tip_id:
            self.tips[self.tip_id] += data

    def handle_endtag(self, tag):
        if tag == 'tool-tip':
            self.tip_id = None


def parse_calendar(html):
    parser = CalendarParser()
    parser.feed(html)
    days = []
    for cell_id, cell in parser.cells.items():
        label = parser.tips.get(cell_id, '').strip()
        match = re.search(r'(No|[\d,]+)\s+contributions?\b', label)
        if match:
            count = 0 if match.group(1).lower() == 'no' else int(match.group(1).replace(',', ''))
        else:
            count = cell['level'] * 2 if cell['level'] > 0 else 0
        days.append({**cell, 'count': count})
    days.sort(key=lambda d: d['date'])
    return days


def fetch_stars_and_commits(fallback_stars=61, fallback_commits=1070):
    stars = fallback_stars
    commits = fallback_commits
    token = os.environ.get('GITHUB_TOKEN')
    headers = {'User-Agent': f'{USER}-profile/1.0'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        req = Request(f'https://api.github.com/users/{USER}/repos?per_page=100', headers=headers)
        with urlopen(req, timeout=15) as resp:
            repos = json.loads(resp.read().decode('utf-8'))
            if isinstance(repos, list):
                stars = sum(r.get('stargazers_count', 0) for r in repos)
    except Exception:
        pass

    try:
        headers_commits = dict(headers)
        headers_commits['Accept'] = 'application/vnd.github.cloak-preview+json'
        req2 = Request(f'https://api.github.com/search/commits?q=author:{USER}', headers=headers_commits)
        with urlopen(req2, timeout=15) as resp2:
            data = json.loads(resp2.read().decode('utf-8'))
            if 'total_count' in data:
                commits = data['total_count']
    except Exception:
        pass

    return stars, commits


def fetch_snapshot(prev_snapshot=None):
    url = f'https://github.com/users/{USER}/contributions'
    request = Request(url, headers={'User-Agent': f'{USER}-profile/1.0', 'Accept': 'text/html'})
    with urlopen(request, timeout=30) as response:
        days = parse_calendar(response.read().decode('utf-8'))
    prev_stars = prev_snapshot.get('total_stars', 61) if prev_snapshot else 61
    prev_commits = prev_snapshot.get('total_commits', 1070) if prev_snapshot else 1070
    stars, commits = fetch_stars_and_commits(prev_stars, prev_commits)
    today = datetime.now(timezone.utc).date()
    return {
        'username': USER,
        'source': url,
        'snapshot_date': today.isoformat(),
        'total_stars': stars,
        'total_commits': commits,
        'days': days,
    }


def longest_streak(days):
    best = run = 0
    for d in days:
        run = run + 1 if d['count'] else 0
        best = max(best, run)
    return best


def pretty(d):
    return f'{d.day} {d.strftime("%b")} {d.year}'


def plural(n, word):
    return f'{n:,} {word}{"" if n == 1 else "s"}'


# ---------------------------------------------------------------- svg helpers

def text(x, y, value, size=16, color='fg', extra=''):
    return f'<text x="{x}" y="{y}" class="{color}" font-size="{size}" {extra}>{escape(str(value))}</text>'


def line(x1, y1, x2, y2, cls='draw-line', extra=''):
    d = f'M{x1} {y1}H{x2}' if y1 == y2 else f'M{x1} {y1}L{x2} {y2}'
    extra_str = f' {extra}' if extra else ''
    return f'<path d="{d}" class="{cls}"{extra_str}/>'


def svg(body, theme, height, title, desc, defs=''):
    t = THEMES[theme]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {height}" width="1200" height="{height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>
<defs>{defs}</defs>
<style>
text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
.fg {{fill:{t['fg']}}} .muted {{fill:{t['muted']}}} .blue {{fill:{t['blue']}}} .gold {{fill:{t['gold']}}}
.mono {{font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;letter-spacing:1px}}
.rule {{fill:none;stroke:{t['line']};stroke-width:1}}
.fade-up {{animation:fadeUp .7s cubic-bezier(0.16, 1, 0.3, 1) both}}
.fade-in {{animation:fadeIn .6s cubic-bezier(0.16, 1, 0.3, 1) both}}
.card-enter {{animation:cardEnter .8s cubic-bezier(0.16, 1, 0.3, 1) both}}
.draw-line {{fill:none;stroke:{t['line']};stroke-width:1;stroke-dasharray:1;stroke-dashoffset:1;animation:draw .9s cubic-bezier(0.16, 1, 0.3, 1) both}}
.cursor {{animation:cursorBlink 1.1s ease-in-out infinite;animation-delay:1.1s}}
.sweep {{fill:none;stroke:{t['accent']};stroke-width:2;stroke-linejoin:round;stroke-linecap:round;stroke-dasharray:1 1;animation:draw 1.6s cubic-bezier(0.16, 1, 0.3, 1) both}}
.cell-reveal {{animation:cellArrive .55s cubic-bezier(0.16, 1, 0.3, 1) both}}
@keyframes fadeUp {{from {{opacity:0;transform:translateY(8px)}} to {{opacity:1;transform:translateY(0)}}}}
@keyframes fadeIn {{from {{opacity:0}} to {{opacity:1}}}}
@keyframes cardEnter {{from {{opacity:0;transform:translateY(10px)}} to {{opacity:1;transform:translateY(0)}}}}
@keyframes draw {{from {{stroke-dashoffset:1;opacity:0}} to {{stroke-dashoffset:0;opacity:1}}}}
@keyframes cursorBlink {{0%,100% {{opacity:1}} 50% {{opacity:0}}}}
@keyframes cellArrive {{from {{opacity:0;transform:translateY(4px)}} to {{opacity:1;transform:translateY(0)}}}}
@media (prefers-reduced-motion:reduce) {{.fade-up,.fade-in,.card-enter,.draw-line,.cursor,.sweep,.cell-reveal {{animation:none!important;opacity:1!important;transform:none!important;stroke-dashoffset:0!important}}}}
</style>
<rect x=".5" y=".5" width="1199" height="{height - 1}" rx="12" fill="{t['bg']}" stroke="{t['line']}"/>
{body}
</svg>\n'''


# ---------------------------------------------------------------- hero

def hero(theme):
    t = THEMES[theme]
    
    # Left typography (smooth staggered cascade)
    b = text(48, 150, 'Paras', 114, 'fg fade-up', 'font-weight="700" letter-spacing="-5" style="animation-delay:.08s"')
    b += text(48, 266, 'Shenmare.', 114, 'fg fade-up', 'font-weight="700" letter-spacing="-5" style="animation-delay:.18s"')
    b += text(50, 332, 'Mobile, web & creative systems.', 22, 'blue fade-up', 'letter-spacing="-.3" style="animation-delay:.32s"')
    b += text(50, 374, 'Flutter · Next.js · Swift', 16, 'muted mono fade-up', 'style="animation-delay:.44s"')
    
    # Right Side: Minimal Aesthetic Developer Console (x=660, y=50, w=490, h=340, rx=14)
    px, py, pw, ph = 660, 50, 490, 340
    b += f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="14" fill="{t["panel"]}" stroke="{t["line"]}" stroke-width="1" class="card-enter" style="animation-delay:.12s"/>'
    
    # Top bar: macOS window buttons & filename
    b += f'<circle cx="{px + 20}" cy="{py + 20}" r="3.5" fill="#ff5f56" class="fade-in" style="animation-delay:.28s"/>'
    b += f'<circle cx="{px + 32}" cy="{py + 20}" r="3.5" fill="#ffbd2e" class="fade-in" style="animation-delay:.35s"/>'
    b += f'<circle cx="{px + 44}" cy="{py + 20}" r="3.5" fill="#27c93f" class="fade-in" style="animation-delay:.42s"/>'
    b += text(px + 62, py + 24, 'client.config.ts', 11, 'muted mono fade-in', 'font-weight="500" style="animation-delay:.46s"')
    b += f'<path d="M{px} {py + 40}H{px + pw}" pathLength="1" class="draw-line" style="animation-delay:.38s"/>'
    
    # Code Content with Syntax Highlighting (staggered cascade)
    cy = py + 40
    b += f'<text x="{px + 24}" y="{cy + 42}" class="mono fade-up" font-size="11.5" style="animation-delay:.52s"><tspan fill="{t["accent"]}">export const</tspan> <tspan fill="{t["fg"]}">client</tspan> <tspan fill="{t["muted"]}">=</tspan> <tspan fill="{t["muted"]}">{{</tspan></text>'
    b += f'<text x="{px + 40}" y="{cy + 70}" class="mono fade-up" font-size="11.5" style="animation-delay:.62s"><tspan fill="{t["blue"]}">focus:</tspan>    <tspan fill="{t["fg"]}">"Mobile, web &amp; creative systems"</tspan><tspan fill="{t["muted"]}">,</tspan></text>'
    b += f'<text x="{px + 40}" y="{cy + 98}" class="mono fade-up" font-size="11.5" style="animation-delay:.72s"><tspan fill="{t["blue"]}">pattern:</tspan>  <tspan fill="{t["fg"]}">"MVVM · Reactive Streams · Clean Code"</tspan><tspan fill="{t["muted"]}">,</tspan></text>'
    b += f'<text x="{px + 40}" y="{cy + 126}" class="mono fade-up" font-size="11.5" style="animation-delay:.82s"><tspan fill="{t["blue"]}">platform:</tspan> <tspan fill="{t["fg"]}">"iOS · Android · Modern Web · macOS"</tspan><tspan fill="{t["muted"]}">,</tspan></text>'
    b += f'<text x="{px + 40}" y="{cy + 154}" class="mono fade-up" font-size="11.5" style="animation-delay:.92s"><tspan fill="{t["blue"]}">status:</tspan>   <tspan fill="{t["gold"]}">"Available for collaboration"</tspan><tspan fill="{t["gold"]}" class="cursor">|</tspan></text>'
    b += f'<text x="{px + 24}" y="{cy + 182}" class="mono fade-up" font-size="11.5" style="animation-delay:1.02s"><tspan fill="{t["muted"]}">}};</tspan></text>'
    
    # Panel Footer: 3 Clean Pillars (Mobile, Web, Systems)
    fy = py + ph - 74
    b += f'<path d="M{px} {fy}H{px + pw}" pathLength="1" class="draw-line" style="animation-delay:.95s"/>'
    
    col_w = pw / 3
    # Pillar 1: Mobile
    b += f'<g class="fade-up" style="animation-delay:1.08s">'
    b += text(px + 24, fy + 26, 'MOBILE', 10, 'muted mono', 'font-weight="600"')
    b += text(px + 24, fy + 48, 'Flutter & Dart', 13, 'fg', 'font-weight="600"')
    b += '</g>'
    
    # Pillar 2: Web
    b += f'<g class="fade-up" style="animation-delay:1.18s">'
    b += text(px + col_w + 12, fy + 26, 'WEB', 10, 'muted mono', 'font-weight="600"')
    b += text(px + col_w + 12, fy + 48, 'Next.js & React', 13, 'fg', 'font-weight="600"')
    b += '</g>'
    
    # Pillar 3: Systems
    b += f'<g class="fade-up" style="animation-delay:1.28s">'
    b += text(px + col_w * 2 + 12, fy + 26, 'SYSTEMS', 10, 'muted mono', 'font-weight="600"')
    b += text(px + col_w * 2 + 12, fy + 48, 'macOS & Swift', 13, 'fg', 'font-weight="600"')
    b += '</g>'
    
    return svg(b, theme, 440, 'Paras Shenmare — Mobile, web & creative systems.',
               'Minimalist developer console showing client architecture spec, engineering principles, and core pillars.')


# ---------------------------------------------------------------- activity

def activity(snapshot, theme):
    t = THEMES[theme]
    days = snapshot['days']
    total = sum(d['count'] for d in days)
    active = sum(d['count'] > 0 for d in days)
    streak = longest_streak(days)
    stars = snapshot.get('total_stars', 61)
    commits = snapshot.get('total_commits', 1070)
    first = date.fromisoformat(days[0]['date'])
    last = date.fromisoformat(days[-1]['date'])
    sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    n_weeks = (last - sunday).days // 7 + 1
    busiest = max(days, key=lambda d: d['count'])

    x0, x1, top = 84, 1152, 226
    pitch = (x1 - x0) / n_weeks
    cell = min(17, pitch - 4)
    grid_bottom = top + 6 * pitch + cell

    b = text(48, 70, 'A look at my work.', 30, 'fg fade-up', 'font-weight="600" letter-spacing="-.7" style="animation-delay:.08s"')
    b += text(48, 96, 'One year of daily iterations, code reviews, and releases.', 13.5, 'muted fade-up', 'style="animation-delay:.18s"')
    stats = [
        (1152, f'{commits:,}', 'Total commits', 38, 'blue', '.46s'),
        (1025, f'{stars:,}', 'Stars earned', 38, 'gold', '.40s'),
        (895, f'{total:,}', 'Contributions (yr)', 26, 'fg', '.34s'),
        (755, f'{active}', 'Active days (yr)', 26, 'fg', '.28s'),
        (625, f'{streak}', 'Best streak (yr)', 26, 'fg', '.22s'),
    ]
    for x, value, label, size, color, delay in stats:
        b += text(x, 70, value, size, f'{color} fade-up', f'text-anchor="end" font-weight="600" letter-spacing="-1" style="animation-delay:{delay}"')
        b += text(x, 94, label, 12, 'muted fade-up', f'text-anchor="end" style="animation-delay:{delay}"')

    weeks = [0] * n_weeks
    for d in days:
        weeks[((date.fromisoformat(d['date']) - sunday).days) // 7] += d['count']
    peak = max(weeks) or 1
    peak_i = weeks.index(max(weeks))
    base, height = 190, 46
    pts = [(x0 + i * pitch + cell / 2, base - n / peak * height) for i, n in enumerate(weeks)]
    path = 'M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in pts)
    area = f'{path} L{pts[-1][0]:.2f} {base} L{pts[0][0]:.2f} {base} Z'
    b += line(x0, base, x1, base, 'draw-line', 'pathLength="1" style="animation-delay:.28s"')
    b += f'<path d="{area}" fill="url(#fade)" class="fade-in" style="animation-delay:.42s"/>'
    b += f'<path d="{path}" pathLength="1" class="sweep" style="animation-delay:.35s"/>'
    px, py = pts[peak_i]
    b += f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3.5" fill="{t["accent"]}" stroke="{t["bg"]}" stroke-width="2" class="fade-in" style="animation-delay:.75s"/>'
    anchor_x = min(max(px, x0 + 90), x1 - 90)
    b += text(f'{anchor_x:.2f}', f'{py - 12:.2f}', f'Peak week: {peak:,}', 12, 'muted fade-in', 'text-anchor="middle" style="animation-delay:.75s"')

    if px < (x0 + x1) / 2:
        b += text(x1, 134, 'Weekly totals', 12, 'muted fade-in', 'text-anchor="end" style="animation-delay:.32s"')
    else:
        b += text(x0, 134, 'Weekly totals', 12, 'muted fade-in', 'style="animation-delay:.32s"')

    previous = -99
    for i in range(n_weeks):
        start = sunday + timedelta(weeks=i)
        if start.day <= 7 and i - previous > 2 and i < n_weeks - 1:
            m_delay = f'{.35 + (i / n_weeks) * .25:.2f}s'
            b += text(f'{x0 + i * pitch:.2f}', top - 12, start.strftime('%b'), 12, 'muted fade-in', f'style="animation-delay:{m_delay}"')
            previous = i
    for row, name in ((1, 'Mon'), (3, 'Wed'), (5, 'Fri')):
        d_delay = f'{.38 + row * .04:.2f}s'
        b += text(48, f'{top + row * pitch + cell / 2 + 4:.2f}', name, 12, 'muted fade-in', f'style="animation-delay:{d_delay}"')

    for d in days:
        day = date.fromisoformat(d['date'])
        col, row = divmod((day - sunday).days, 7)
        x, y = x0 + col * pitch, top + row * pitch
        ring = f' stroke="{t["accent"]}" stroke-width="1.5"' if d is busiest and d['count'] else ''
        tip = f'{pretty(day)}: {plural(d["count"], "contribution")}'
        c_delay = f'{.38 + col * .012 + row * .018:.3f}s'
        b += (f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" rx="3" '
              f'fill="{t["ramp"][d["level"]]}"{ring} class="cell-reveal" '
              f'style="animation-delay:{c_delay}"><title>{escape(tip)}</title></rect>')

    fy = grid_bottom + 34
    b += line(48, fy - 26, x1, fy - 26, 'draw-line', 'pathLength="1" style="animation-delay:.82s"')
    b += text(48, fy, f'{pretty(first)} to {pretty(last)}  ·  updated {snapshot["snapshot_date"]}', 12, 'muted fade-in', 'style="animation-delay:.92s"')
    b += f'<g class="fade-in" style="animation-delay:1.02s">'
    b += text(x1, fy, 'More', 12, 'muted', 'text-anchor="end"')
    for i, color in enumerate(t['ramp']):
        b += f'<rect x="{x1 - 46 - (5 - i) * 17:.0f}" y="{fy - 11}" width="12" height="12" rx="3" fill="{color}"/>'
    b += text(x1 - 46 - 5 * 17 - 6, fy, 'Less', 12, 'muted', 'text-anchor="end"')
    b += '</g>'

    height_total = int(fy + 28)
    defs = (f'<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{t["accent"]}" stop-opacity=".28"/>'
            f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></linearGradient>')
    desc = (f'{total:,} contributions across {active} active days, {stars} stars earned, and {commits:,} commits. '
            f'Longest streak {streak} days. Busiest day {pretty(date.fromisoformat(busiest["date"]))} '
            f'with {busiest["count"]}. Weekly totals are drawn above the calendar. '
            f'Snapshot {snapshot["snapshot_date"]}.')
    return svg(b, theme, height_total, 'A look at my work — public GitHub activity', desc, defs)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'data/contributions.json'

    if args.fetch or not target.exists():
        try:
            prev = json.loads(target.read_text()) if target.exists() else None
            snapshot = fetch_snapshot(prev)
        except Exception as e:
            if target.exists():
                print(f"Fetch failed ({e}), loading local snapshot...")
                snapshot = json.loads(target.read_text())
            else:
                raise e
    else:
        snapshot = json.loads(target.read_text())

    output = {}
    for theme in THEMES:
        output[f'hero-{theme}.svg'] = hero(theme)
        output[f'activity-{theme}.svg'] = activity(snapshot, theme)

    (ROOT / 'assets').mkdir(exist_ok=True)
    target.parent.mkdir(exist_ok=True)
    for name, content in output.items():
        path = ROOT / 'assets' / name
        path.write_text(content, encoding='utf-8')
    target.write_text(json.dumps(snapshot, indent=2) + '\n', encoding='utf-8')
    print(f'Rendered {len(output)} SVGs from {len(snapshot["days"])} verified days; {sum(d["count"] for d in snapshot["days"]):,} contributions.')


if __name__ == '__main__':
    main()

