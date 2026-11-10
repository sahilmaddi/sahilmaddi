#!/usr/bin/env python3
"""Render the profile README cards into cards/ and write README.md.

    python scripts/render_readme_cards.py           # animated cards
    STATIC=1 python scripts/render_readme_cards.py  # final frame only (for screenshots)

Reads config.json, data/contributions.json and data/repos.json.
Standard library only, so the GitHub Action needs no pip install.

What survives in an SVG shown through <img>: its own <style> block (CSS keyframes),
SMIL (<animate>, <set>) and fonts embedded as data URIs. No scripts, no network.
"""
import base64
import datetime as dt
import html
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.environ.get("STATIC") == "1"
CARDS = os.environ.get("CARDS_DIR", os.path.join(ROOT, "cards"))
DATA = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
README = os.environ.get("README_PATH", os.path.join(ROOT, "README.md"))


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


CFG = load(os.path.join(ROOT, "config.json"))
C = CFG["colors"]
METRICS = load(os.path.join(ROOT, "fonts", "metrics.json"))

# ----------------------------------------------------------------------------- fonts

FACES = {
    "sans400": ("Inter", 400, "sans-400.woff"),
    "sans600": ("Inter", 600, "sans-600.woff"),
    "sans700": ("Inter", 700, "sans-700.woff"),
    "mono": ("Mono", 400, "mono-400.woff"),
}
_B64 = {}


def font_face(key):
    family, weight, fn = FACES[key]
    if fn not in _B64:
        with open(os.path.join(ROOT, "fonts", fn), "rb") as f:
            _B64[fn] = base64.b64encode(f.read()).decode()
    return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/woff;base64,{_B64[fn]}) format('woff')}}")


def tw(text, key, size, spacing=0.0):
    """Width of text in px, from the subset font's advance widths."""
    m = METRICS[FACES[key][2]]
    adv, upm = m["adv"], m["upm"]
    w = sum(adv.get(ch, adv.get("n", upm * 0.55)) for ch in text) * size / upm
    return w + spacing * max(0, len(text) - 1)


def esc(s):
    return html.escape(str(s), quote=True)


def wrap(text, key, size, width, max_lines=99):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if not cur or tw(trial, key, size) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and tw(last + "…", key, size) > width:
            last = last[:-1]
        lines[-1] = last.rstrip(" ,.;:·") + "…"
    return lines


def clip(text, key, size, width):
    if tw(text, key, size) <= width:
        return text
    while text and tw(text + "…", key, size) > width:
        text = text[:-1]
    return text.rstrip(" ,.;:·") + "…"


def mix(a, b, t):
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


# ----------------------------------------------------------------------------- animation

EASE = "cubic-bezier(.2,.7,.2,1)"
KEYFRAMES = (
    "@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}"
    "@keyframes fade{from{opacity:0}to{opacity:1}}"
    "@keyframes pop{0%{opacity:0;transform:scale(.2)}65%{opacity:1;transform:scale(1.2)}100%{opacity:1;transform:scale(1)}}"
    "@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
    "@keyframes ring{0%{opacity:.75;transform:scale(.5)}100%{opacity:0;transform:scale(3.2)}}"
    "@keyframes swing{0%{opacity:0;transform:translateY(150px) rotate(-9deg)}"
    "55%{opacity:1;transform:translateY(-12px) rotate(2deg)}"
    "78%{transform:translateY(5px) rotate(-.6deg)}100%{opacity:1;transform:none}}"
    "@keyframes sweep{0%{transform:translateX(0)}24%,100%{transform:translateX(560px)}}"
    "@keyframes nudge{0%,70%,100%{transform:translate(0,0)}80%{transform:translate(3px,-3px)}90%{transform:translate(0,0)}}"
    "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}"
    "@keyframes type{from{transform:translateX(0)}to{transform:translateX(100%)}}"
    "@keyframes on{from,to{opacity:1}}"
    "@keyframes off{from,to{opacity:0}}"
)


# Each card is its own image with its own clock, so cards further down the page
# start later: hero, then the graph, the bars, the tiles and the repos.
T0 = 0.0
CARD_START = {"hero": 0.0, "graph": 0.7, "activity": 1.3, "tiles": 1.9, "repos": 2.5}


def start(card):
    global T0
    T0 = CARD_START[card]


def anim(name, dur, delay, ease=EASE, tail="both"):
    """Inline animation style attribute. Empty in STATIC mode."""
    if STATIC:
        return ""
    return f' style="animation:{name} {dur}s {ease} {T0 + delay:.3f}s {tail}"'


def doc(w, h, body, fonts, label, defs=""):
    css = "".join(font_face(k) for k in fonts)
    css += (".s{font-family:'Inter',ui-sans-serif,system-ui,sans-serif}"
            ".m{font-family:'Mono',ui-monospace,SFMono-Regular,Menlo,monospace}"
            ".fb{transform-box:fill-box;transform-origin:center}"
            ".fbb{transform-box:fill-box;transform-origin:50% 100%}"
            ".still{display:none}")
    if STATIC:
        css += ".still{display:inline}"
    else:
        css += KEYFRAMES
        # Everything switches off for people who ask for less motion. SMIL can't be
        # stopped from CSS, so SMIL parts live in .motion and have a .still twin.
        css += ("@media (prefers-reduced-motion:reduce){*{animation:none!important}"
                f".motion,.cover{{display:none}}.still{{display:inline}}.shine{{fill:{C['text']}}}}}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'
            f"<title>{esc(label)}</title><style>{css}</style>"
            f"{('<defs>' + defs + '</defs>') if defs else ''}{body}</svg>")


def frames(final_text_fn, steps, begin, dur, attrs, cls="s"):
    """A count-up made of SMIL <set> frames: one <text> per value, each visible briefly.
    CSS can't change text content, so this is the only way inside an <img>."""
    still = f'<text class="{cls} still" {attrs}>{esc(final_text_fn(steps[-1]))}</text>'
    if STATIC:
        return f'<text class="{cls}" {attrs}>{esc(final_text_fn(steps[-1]))}</text>'
    # dedupe consecutive values
    seq = []
    for v in steps:
        if not seq or seq[-1] != v:
            seq.append(v)
    n = len(seq)
    step = dur / max(1, n - 1)
    out = []
    for i, v in enumerate(seq):
        t = T0 + begin + i * step
        if i < n - 1:
            s = f'<set attributeName="visibility" to="visible" begin="{t:.3f}s" dur="{step:.3f}s"/>'
        else:
            s = f'<set attributeName="visibility" to="visible" begin="{t:.3f}s" fill="freeze"/>'
        out.append(f'<text class="{cls}" visibility="hidden" {attrs}>{esc(final_text_fn(v))}{s}</text>')
    return f'<g class="motion">{"".join(out)}</g>{still}'


def countup_steps(value, n=18):
    return [round(value * (1 - (1 - k / (n - 1)) ** 3)) for k in range(n)]


def card_frame(w, h, r=18):
    return (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{r}" '
            f'fill="{C["card"]}" stroke="{C["border"]}"/>')


def arrow(cx, cy, size, color, width=2.0):
    s = size / 2
    return (f'<path d="M{cx - s:.1f} {cy + s:.1f} L{cx + s:.1f} {cy - s:.1f} '
            f'M{cx - s * 0.35:.1f} {cy - s:.1f} L{cx + s:.1f} {cy - s:.1f} L{cx + s:.1f} {cy + s * 0.35:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')


# ----------------------------------------------------------------------------- data

def load_days():
    data = load(os.path.join(DATA, "contributions.json"))
    if not data or not data.get("days"):
        raise SystemExit("data/contributions.json is missing; run scripts/fetch_github_data.py first")
    days = {}
    for d in data["days"]:
        days[dt.date.fromisoformat(d["date"])] = (int(d["count"]), d.get("level"))
    return data, days


def stats(days, total=None):
    """Streaks and monthly sums over the calendar GitHub returned (about a year)."""
    last = max(days)
    first = min(days)
    year = [last - dt.timedelta(days=i) for i in range((last - first).days + 1)]
    counts = [days.get(d, (0, None))[0] for d in year]  # newest first
    total = total if total is not None else sum(counts)
    active = sum(1 for c in counts if c > 0)
    # current streak: consecutive active days ending today, or yesterday if today is empty
    cur, i = 0, 0
    if counts and counts[0] == 0:
        i = 1
    while i < len(counts) and counts[i] > 0:
        cur += 1
        i += 1
    longest = run = 0
    for c in reversed(counts):
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    busiest = max(year, key=lambda d: (days.get(d, (0,))[0], d))
    busiest_n = days.get(busiest, (0,))[0]
    # last 12 calendar months, oldest first, including the current one
    months = []
    y, m = last.year, last.month
    for _ in range(12):
        months.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    months.reverse()
    per_month = []
    for (yy, mm) in months:
        per_month.append(((yy, mm), sum(c for d, (c, _) in days.items() if d.year == yy and d.month == mm)))
    return dict(last=last, total=total, active=active, current=cur, longest=longest,
                busiest=busiest, busiest_n=busiest_n, per_month=per_month)


def featured_repos():
    data = load(os.path.join(DATA, "repos.json"), {}) or {}
    by_name = {r["name"]: r for r in (data.get("pinned", []) + data.get("recent", []))}
    names = CFG.get("featured_repos") or [r["name"] for r in data.get("pinned", [])]
    if not names:
        names = [r["name"] for r in data.get("recent", []) if not r.get("fork")]
    out = []
    login = data.get("login", "")
    for name in names[: CFG.get("max_repos", 4)]:
        r = dict(by_name.get(name, {"name": name, "url": f"https://github.com/{login}/{name}"}))
        note = CFG.get("repo_notes", {}).get(name, {})
        r["title"] = note.get("title") or r["name"]
        r["description"] = note.get("description") or r.get("description") or ""
        r["stack"] = note.get("stack") or r.get("topics") or []
        out.append(r)
    return out


# ----------------------------------------------------------------------------- code

import re as _re

_TOKENS = _re.compile(r'(?P<comment>//.*$)|(?P<string>"[^"]*")|(?P<annotation>@\w+)'
                      r'|(?P<keyword>\b(?:public|private|class|record|int|long|boolean|true|false|new|final|static|void|return)\b)'
                      r'|(?P<type>\b[A-Z]\w*\b)|(?P<number>\b\d+\b)')


def highlight(line):
    """Java-ish syntax colours as tspans."""
    colours = {"comment": C["faint"], "string": C["accent_hi"], "annotation": C["accent"],
               "keyword": "#7dd3fc", "type": C["live"], "number": C["accent"]}
    out, pos = [], 0
    for m in _TOKENS.finditer(line):
        if m.start() > pos:
            out.append(esc(line[pos:m.start()]))
        out.append(f'<tspan fill="{colours[m.lastgroup]}">{esc(m.group())}</tspan>')
        pos = m.end()
    out.append(esc(line[pos:]))
    return "".join(out)


# ----------------------------------------------------------------------------- cards

def hero():
    W = 840
    x0 = 48
    body = []
    defs = []

    # right side of the hero: "portrait" (ASCII face in a frame) or "code" (typing Java class)
    side = CFG.get("hero_side", "portrait")

    # portrait card
    rows = []
    P = CFG.get("portrait") or {}
    if side == "portrait" and P.get("file") and os.path.exists(os.path.join(ROOT, P["file"])):
        with open(os.path.join(ROOT, P["file"]), encoding="utf-8") as f:
            rows = [ln.rstrip("\n") for ln in f]
        while rows and not rows[-1].strip():
            rows.pop()
    pcw = P.get("cell", 3.6)        # character cell width
    pch = pcw * 1.6                 # cells are 1.6x taller than wide, matching how the photo was sampled
    pfs = pcw / 0.602               # mono advance is 0.602em
    ppad = 16
    pcols = max((len(r) for r in rows), default=0)

    # code panel
    code = CFG.get("code") or {}
    lines_src = code.get("lines", []) if side == "code" else []
    cfs = 12.5                      # code font size
    adv = cfs * 0.602               # mono advance
    lh = 21
    pad_x, bar_h = 20, 36
    if rows:
        pw, ph = pcols * pcw + ppad * 2, len(rows) * pch + ppad * 2
    elif lines_src:
        pw = max([310] + [len(t) * adv + 2 * pad_x for t in lines_src])
        ph = bar_h + 14 + len(lines_src) * lh + 14
    else:
        pw = ph = 0

    # text column
    col_w = min(420, W - 40 - pw - x0 - 24) if pw else W - 2 * x0
    tag_lines = wrap(CFG["tagline"], "sans400", 15, col_w)
    y_logo = 64
    y_pill = 88
    y_n1 = 182
    y_n2 = y_n1 + 66
    y_role = y_n2 + 38
    y_tag = y_role + 32
    y_meta = y_tag + 22 * (len(tag_lines) - 1) + 30
    H = int(max(y_meta + 44, ph + (72 if rows else 80)))

    # dotted background, like the site
    defs.append('<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
                '<circle cx="2" cy="2" r="1" fill="#ffffff" fill-opacity=".055"/></pattern>')
    body.append(card_frame(W, H, 20))
    body.append(f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="19" fill="url(#dots)"/>')

    # logo  <SahilMaddi />
    body.append(f'<text class="m" x="{x0}" y="{y_logo}" font-size="15" fill="{C["text"]}"{anim("rise", .6, .05)}>'
                f'<tspan fill="{C["accent"]}">&lt;</tspan>{esc(CFG["logo"])}'
                f'<tspan fill="{C["accent"]}"> /&gt;</tspan></text>')

    # status pill with a pulsing dot
    st = CFG["status"]
    pw_pill = 34 + tw(st, "sans600", 12.5) + 16
    cy = y_pill + 14
    body.append(f'<g{anim("rise", .6, .15)}>'
                f'<rect x="{x0}" y="{y_pill}" width="{pw_pill:.1f}" height="28" rx="14" '
                f'fill="{C["live"]}" fill-opacity=".1" stroke="{C["live"]}" stroke-opacity=".28"/>'
                f'<circle class="fb" cx="{x0 + 17}" cy="{cy}" r="3.5" fill="{C["live"]}"'
                f'{anim("ring", 2.0, 1.2, "ease-out", "infinite")}/>'
                f'<circle cx="{x0 + 17}" cy="{cy}" r="3.5" fill="{C["live"]}"/>'
                f'<text class="s" x="{x0 + 30}" y="{cy + 4.5}" font-size="12.5" font-weight="600" fill="{C["live"]}">{esc(st)}</text>'
                f'</g>')

    # name, one line at a time; a shine sweeps across the surname
    first, last = CFG["name"]
    fs_name = 66
    track = -1.8
    body.append(f'<text class="s" x="{x0 - 3}" y="{y_n1}" font-size="{fs_name}" font-weight="700" '
                f'letter-spacing="{track}" fill="{C["text"]}"{anim("rise", .7, .3)}>{esc(first)}</text>')
    lw = tw(last, "sans700", fs_name, track)
    if STATIC:
        fill = C["text"]
    else:
        defs.append(
            f'<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="{x0}" y1="0" x2="{x0 + lw:.1f}" y2="0" '
            f'gradientTransform="translate({-lw:.1f} 0)">'
            f'<stop offset="0" stop-color="{C["text"]}"/><stop offset=".34" stop-color="{C["text"]}"/>'
            f'<stop offset=".5" stop-color="{C["accent"]}"/><stop offset=".58" stop-color="{C["accent_hi"]}"/>'
            f'<stop offset=".7" stop-color="{C["text"]}"/><stop offset="1" stop-color="{C["text"]}"/>'
            f'<animateTransform attributeName="gradientTransform" type="translate" '
            f'values="{-lw:.1f} 0;{lw:.1f} 0;{lw:.1f} 0" keyTimes="0;.24;1" dur="5.5s" begin="1.5s" '
            f'repeatCount="indefinite"/></linearGradient>')
        fill = "url(#shine)"
    body.append(f'<text class="s shine" x="{x0 - 3}" y="{y_n2}" font-size="{fs_name}" font-weight="700" '
                f'letter-spacing="{track}" fill="{fill}"{anim("rise", .7, .45)}>{esc(last)}</text>')

    body.append(f'<text class="m" x="{x0}" y="{y_role}" font-size="15" fill="{C["accent"]}"'
                f'{anim("rise", .6, .6)}>{esc(CFG["role"])}</text>')
    tl = "".join(f'<tspan x="{x0}" dy="{0 if i == 0 else 22}">{esc(t)}</tspan>' for i, t in enumerate(tag_lines))
    body.append(f'<text class="s" x="{x0}" y="{y_tag}" font-size="15" fill="{C["body"]}"'
                f'{anim("rise", .6, .72)}>{tl}</text>')
    body.append(f'<text class="s" x="{x0}" y="{y_meta}" font-size="13" fill="{C["muted"]}"'
                f'{anim("rise", .6, .84)}>{esc(CFG["meta"])}</text>')

    # the portrait prints in row by row, like a slow terminal
    if rows:
        px = W - 40 - pw
        py = (H - ph) / 2
        defs.append(f'<radialGradient id="glow" cx=".5" cy=".5" r=".5">'
                    f'<stop offset="0" stop-color="{C["accent"]}" stop-opacity=".22"/>'
                    f'<stop offset="1" stop-color="{C["accent"]}" stop-opacity="0"/></radialGradient>')
        body.append(f'<ellipse cx="{px + pw / 2:.1f}" cy="{py + ph * .78:.1f}" rx="{pw * .62:.1f}" ry="{ph * .42:.1f}" '
                    f'fill="url(#glow)"{anim("fade", 1.2, .3)}/>')
        body.append(f'<rect x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="{ph:.1f}" rx="26" '
                    f'fill="{C["surface"]}" stroke="{C["border"]}"{anim("fade", .5, .2)}/>')
        out = []
        for i, row in enumerate(rows):
            # spaces collapse in SVG, so place each run of glyphs explicitly
            runs, j = [], 0
            while j < len(row):
                if row[j] == " ":
                    j += 1
                    continue
                k = j
                while k < len(row) and row[k] != " ":
                    k += 1
                runs.append(f'<tspan x="{px + ppad + j * pcw:.1f}">{esc(row[j:k])}</tspan>')
                j = k
            if runs:
                y = py + ppad + (i + 0.78) * pch
                out.append(f'<text y="{y:.1f}"{anim("fade", .16, .45 + i * 0.03, "linear")}>{"".join(runs)}</text>')
        body.append(f'<g class="m" font-size="{pfs:.2f}" fill="{C["body"]}">{"".join(out)}</g>')
        # a terminal cursor that keeps blinking after the print
        cy_cur = py + ppad + len(rows) * pch - pch * 0.15
        body.append(f'<rect x="{px + pw - ppad - pcw * 2:.1f}" y="{cy_cur - pch:.1f}" width="{pcw * 1.6:.1f}" height="{pch * .95:.1f}" '
                    f'fill="{C["accent"]}"{anim("blink", 1.0, .45 + len(rows) * .03, "steps(1)", "infinite")}/>')

    # a terminal window where a Java class about you types in, line by line
    if lines_src:
        px = W - 40 - pw
        py = (H - ph) / 2
        defs.append(f'<radialGradient id="glow" cx=".5" cy=".5" r=".5">'
                    f'<stop offset="0" stop-color="{C["accent"]}" stop-opacity=".18"/>'
                    f'<stop offset="1" stop-color="{C["accent"]}" stop-opacity="0"/></radialGradient>'
                    f'<clipPath id="pane"><rect x="{px:.1f}" y="{py + bar_h:.1f}" width="{pw:.1f}" height="{ph - bar_h:.1f}"/></clipPath>')
        body.append(f'<ellipse cx="{px + pw / 2:.1f}" cy="{py + ph * .8:.1f}" rx="{pw * .65:.1f}" ry="{ph * .45:.1f}" '
                    f'fill="url(#glow)"{anim("fade", 1.2, .3)}/>')
        pane = [f'<rect x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="{ph:.1f}" rx="16" fill="{C["surface"]}" stroke="{C["border"]}"/>',
                f'<line x1="{px:.1f}" y1="{py + bar_h:.1f}" x2="{px + pw:.1f}" y2="{py + bar_h:.1f}" stroke="{C["border"]}"/>']
        for k, col in enumerate(("#f87171", C["accent"], C["live"])):
            pane.append(f'<circle cx="{px + 20 + k * 16:.1f}" cy="{py + bar_h / 2:.1f}" r="5" fill="{col}" fill-opacity=".85"/>')
        pane.append(f'<text class="m" x="{px + pw / 2:.1f}" y="{py + bar_h / 2 + 4:.1f}" font-size="11.5" '
                    f'text-anchor="middle" fill="{C["faint"]}">{esc(code.get("file", ""))}</text>')
        body.append(f'<g{anim("rise", .6, .2)}>{"".join(pane)}</g>')

        text, covers = [], []
        t = .75                     # typing starts once the panel is in
        per_char, gap = .013, .07
        for i, src in enumerate(lines_src):
            x = px + pad_x
            y = py + bar_h + 14 + (i + 0.75) * lh
            text.append(f'<text x="{x:.1f}" y="{y:.1f}" xml:space="preserve">{highlight(src)}</text>')
            n = len(src.rstrip())
            if n == 0 or STATIC:
                continue
            dur = n * per_char
            wline = n * adv
            last = i == len(lines_src) - 1
            cur_anim = (f"on .01s step-end {T0 + t:.3f}s forwards, "
                        + (f"blink 1s steps(1) {T0 + t + dur:.3f}s infinite" if last
                           else f"off .01s step-end {T0 + t + dur:.3f}s forwards"))
            # a panel-coloured cover slides off the line one character at a time,
            # dragging the cursor with it
            covers.append(f'<g class="fb cover" style="animation:type {dur:.3f}s steps({n}, end) {T0 + t:.3f}s both">'
                          f'<rect x="{x - 1:.1f}" y="{y - lh + 6:.1f}" width="{wline + 2:.1f}" height="{lh:.1f}" fill="{C["surface"]}"/>'
                          f'<rect x="{x:.1f}" y="{y - 12:.1f}" width="{adv:.1f}" height="15" fill="{C["accent"]}" opacity="0" '
                          f'style="animation:{cur_anim}"/></g>')
            t += dur + gap
        if STATIC and lines_src:
            n = len(lines_src[-1].rstrip())
            y = py + bar_h + 14 + (len(lines_src) - 1 + 0.75) * lh
            covers.append(f'<rect x="{px + pad_x + n * adv + 2:.1f}" y="{y - 12:.1f}" width="{adv:.1f}" height="15" fill="{C["accent"]}"/>')
        body.append(f'<g class="m" font-size="{cfs}" fill="{C["body"]}"{anim("fade", .4, .3)}>{"".join(text)}</g>'
                    f'<g clip-path="url(#pane)">{"".join(covers)}</g>')

    label = f'{first} {last}, {CFG["role"]}. {CFG["tagline"]}'
    return doc(W, H, "".join(body), ["sans400", "sans600", "sans700", "mono"], label, "".join(defs))


def graph(data, days, s):
    W, H = 840, 236
    x_left = 40
    body = [card_frame(W, H)]
    last = s["last"]
    start = last - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)   # back to Sunday
    weeks = ((last - start).days // 7) + 1

    # header
    body.append(f'<g{anim("rise", .6, .1)}>'
                f'<text class="s" x="{x_left}" y="46" font-size="17" font-weight="600" fill="{C["text"]}">Contributions</text>'
                f'<text class="m" x="{x_left}" y="68" font-size="11.5" fill="{C["faint"]}">'
                f'last 12 months · updated {last.strftime("%b")} {last.day}</text></g>')
    total = s["total"]
    body.append(frames(lambda v: f"{v:,}", countup_steps(total), .35, .9,
                       f'x="{W - x_left}" y="52" font-size="30" font-weight="700" '
                       f'text-anchor="end" fill="{C["accent"]}"'))
    body.append(f'<text class="s" x="{W - x_left}" y="70" font-size="12.5" text-anchor="end" fill="{C["muted"]}"'
                f'{anim("fade", .6, .3)}>contributions</text>')

    # grid
    x0, y0 = 78, 100
    pitch = (W - x_left - x0) / weeks
    cell = pitch - 3
    levels = [C["empty"]] + [mix(C["empty"], C["accent"], t) for t in (.32, .55, .78, 1.0)]
    nz = sorted(c for c, _ in days.values() if c > 0)
    def level_of(count, given):
        if given is not None:
            return int(given)
        if count <= 0 or not nz:
            return 0
        q = [nz[int(len(nz) * f)] for f in (.25, .5, .75)]
        return 1 + sum(count > t for t in q)
    cells = []
    month_marks = []
    prev_month = None
    for w in range(weeks):
        for r in range(7):
            d = start + dt.timedelta(days=w * 7 + r)
            if d > last:
                continue
            if r == 0 or d == start:
                if d.month != prev_month:
                    month_marks.append((w, d))
                    prev_month = d.month
            count, lv = days.get(d, (0, 0))
            lv = level_of(count, lv)
            x = x0 + w * pitch
            y = y0 + r * pitch
            cells.append(f'<rect class="fb" x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2.5" '
                         f'fill="{levels[lv]}"{anim("pop", .34, .55 + w * .021 + r * .012)}>'
                         f'<title>{count} on {d.isoformat()}</title></rect>')
    body.append("".join(cells))
    # month labels, skipping any too close to the previous one
    lab, last_w = [], -9
    for w, d in month_marks:
        if w - last_w < 3 or w > weeks - 2:
            continue
        lab.append(f'<text x="{x0 + w * pitch:.1f}" y="{y0 - 10}">{d.strftime("%b")}</text>')
        last_w = w
    body.append(f'<g class="m" font-size="10" fill="{C["faint"]}"{anim("fade", .6, .4)}>{"".join(lab)}'
                + "".join(f'<text x="{x_left}" y="{y0 + r * pitch + cell - 1.5:.1f}">{n}</text>'
                          for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri")))
                + "</g>")
    # legend, right-aligned under the grid
    more_w = tw("more", "mono", 10)
    lx = W - x_left - more_w - 6 - 5 * 14 + 3
    ly = y0 + 7 * pitch + 20
    legend = "".join(f'<rect x="{lx + i * 14:.1f}" y="{ly - 9:.1f}" width="11" height="11" rx="2.5" fill="{c}"/>'
                     for i, c in enumerate(levels))
    body.append(f'<g class="m" font-size="10" fill="{C["faint"]}"{anim("fade", .6, 1.6)}>'
                f'<text x="{lx - 6:.1f}" y="{ly:.1f}" text-anchor="end">less</text>{legend}'
                f'<text x="{W - x_left}" y="{ly:.1f}" text-anchor="end">more</text></g>')
    label = f'Contribution graph: {total} contributions in the last year'
    return doc(W, H, "".join(body), ["sans600", "sans700", "mono"], label)


def activity(s):
    W, H = 840, 262
    x_left = 40
    body = [card_frame(W, H)]
    body.append(f'<g{anim("rise", .6, .1)}>'
                f'<text class="s" x="{x_left}" y="46" font-size="17" font-weight="600" fill="{C["text"]}">Monthly activity</text>'
                f'<text class="m" x="{x_left}" y="68" font-size="11.5" fill="{C["faint"]}">contributions per month</text></g>')

    # bars
    pm = s["per_month"]
    area_l, area_r = x_left, 520
    base = 210
    top = 104
    gap = 10
    bw = (area_r - area_l - gap * (len(pm) - 1)) / len(pm)
    peak = max((v for _, v in pm), default=0)
    best_i = max(range(len(pm)), key=lambda i: (pm[i][1], i)) if peak > 0 else -1
    bars = []
    for i, ((yy, mm), v) in enumerate(pm):
        x = area_l + i * (bw + gap)
        mname = dt.date(yy, mm, 1).strftime("%b")
        is_best = i == best_i
        col = C["accent"] if is_best else C["bar"]
        if v > 0:
            h = max(6, (base - top) * v / peak)
            bars.append(f'<rect class="fbb" x="{x:.1f}" y="{base - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="5" '
                        f'fill="{col}"{anim("grow", .7, .45 + i * .06)}><title>{v} in {mname} {yy}</title></rect>')
        else:
            bars.append(f'<rect x="{x:.1f}" y="{base - 2}" width="{bw:.1f}" height="2" rx="1" fill="{C["empty"]}"/>')
        bars.append(f'<text class="m" x="{x + bw / 2:.1f}" y="{base + 20}" font-size="10" text-anchor="middle" '
                    f'fill="{C["accent"] if is_best else C["faint"]}">{mname}</text>')
        if is_best:
            h = max(6, (base - top) * v / peak)
            bars.append(f'<text class="s fb" x="{x + bw / 2:.1f}" y="{base - h - 9:.1f}" font-size="14" font-weight="700" '
                        f'text-anchor="middle" fill="{C["accent"]}"{anim("pop", .45, .45 + len(pm) * .06 + .45)}>{v}</text>')
    body.append("".join(bars))
    body.append(f'<line x1="556" y1="40" x2="556" y2="{H - 40}" stroke="{C["border"]}"/>')

    # streak stats, 2 x 2
    def plural(n, word):
        return f"{word}" if n == 1 else f"{word}s"
    b = s["busiest"]
    items = [
        ("CURRENT STREAK", f'{s["current"]}', plural(s["current"], "day")),
        ("LONGEST STREAK", f'{s["longest"]}', plural(s["longest"], "day")),
        ("ACTIVE DAYS", f'{s["active"]}', "in the last year"),
        ("BUSIEST DAY", f'{s["busiest_n"]}', f'on {b.strftime("%b")} {b.day}' if s["busiest_n"] else ""),
    ]
    out = []
    for i, (lab, val, unit) in enumerate(items):
        x = 588 + (i % 2) * 126
        y = 92 + (i // 2) * 86
        vw = tw(val, "sans700", 28, -0.5)
        out.append(f'<g{anim("rise", .6, .5 + i * .1)}>'
                   f'<text class="m" x="{x}" y="{y}" font-size="10" letter-spacing="1" fill="{C["faint"]}">{lab}</text>'
                   f'<text class="s" x="{x}" y="{y + 34}" font-size="28" font-weight="700" letter-spacing="-.5" fill="{C["text"]}">{esc(val)}</text>'
                   f'<text class="s" x="{x + vw + 6:.1f}" y="{y + 34}" font-size="12.5" fill="{C["muted"]}">{esc(unit)}</text></g>')
    body.append("".join(out))
    label = (f'Monthly contributions. Current streak {s["current"]} days, longest {s["longest"]}, '
             f'{s["active"]} active days, busiest day {s["busiest_n"]} on {b.isoformat()}')
    return doc(W, H, "".join(body), ["sans600", "sans700", "mono"], label)


def tile(t, i):
    W, H = 272, 300
    ink = C["tile_ink"]
    base = 0.25 + i * 0.16
    defs = (f'<clipPath id="clip"><rect width="{W}" height="{H}" rx="22"/></clipPath>'
            f'<linearGradient id="band" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".45"/>'
            f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    g = [f'<rect width="{W}" height="{H}" rx="22" fill="{t["color"]}"/>']
    g.append(f'<text class="m" x="26" y="46" font-size="12" letter-spacing="2.2" fill="{ink}" fill-opacity=".78">{esc(t["label"])}</text>')

    # arrow in a circle, with a ring that pulses out of the corner on arrival
    ax, ay = W - 40, 40
    g.append(f'<circle class="fb" cx="{ax}" cy="{ay}" r="17" fill="none" stroke="{ink}" stroke-width="2" opacity="0"'
             f'{anim("ring", 1.3, base + .75, "ease-out", "2 forwards")}/>')
    g.append(f'<circle cx="{ax}" cy="{ay}" r="17" fill="{ink}" fill-opacity=".1"/>')
    g.append(f'<g{anim("nudge", 2.6, base + 1.6, "ease-in-out", "infinite")}>{arrow(ax, ay, 11, ink, 2.2)}</g>')

    # the number counts up from zero
    value = t["value"]
    suffix = t.get("suffix", "")
    final = f"{value}{suffix}"
    size = min(104, (W - 52) / max(1e-6, tw(final, "sans700", 1, -0.045)))
    g.append(frames(lambda v: f"{v}{suffix}", countup_steps(value) if isinstance(value, int) else [value],
                    base + .55, .65,
                    f'x="22" y="186" font-size="{size:.0f}" font-weight="700" letter-spacing="{-0.045 * size:.1f}" fill="{ink}"'))
    cap = wrap(t["caption"], "sans600", 15, W - 52, 2)
    g.append(f'<text class="s" x="26" y="{218 if len(cap) == 1 else 212}" font-size="15" font-weight="600" fill="{ink}">'
             + "".join(f'<tspan x="26" dy="{0 if k == 0 else 19}">{esc(c)}</tspan>' for k, c in enumerate(cap))
             + "</text>")
    g.append(f'<line x1="26" y1="250" x2="{W - 26}" y2="250" stroke="{ink}" stroke-opacity=".18"/>')
    g.append(f'<text class="m" x="26" y="276" font-size="11.5" fill="{ink}" fill-opacity=".72">{esc(t["footer"])} →</text>')

    # a shine sweeps across every few seconds
    if not STATIC:
        g.append(f'<g clip-path="url(#clip)"><g transform="rotate(18 {W / 2} {H / 2})">'
                 f'<rect x="-190" y="-120" width="110" height="{H + 240}" fill="url(#band)" '
                 f'style="animation:sweep 6.5s ease-in-out {T0 + base + 1.9:.2f}s infinite"/></g></g>')

    body = f'<g class="fbb"{anim("swing", 1.0, base, "cubic-bezier(.3,.9,.3,1)")}>{"".join(g)}</g>'
    label = f'{t["label"].title()}: {final} {t["caption"]}'
    return doc(W, H, body, ["sans600", "sans700", "mono"], label, defs)


LANG_COLORS = {"Java": "#b07219", "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5"}


def repo_card(r, i):
    W, H = 413, 172
    x0 = 26
    body = [card_frame(W, H, 16)]
    lang = (r.get("language") or {}) if isinstance(r.get("language"), dict) else {"name": r.get("language")}
    lname = lang.get("name")
    lcol = lang.get("color") or LANG_COLORS.get(lname or "", C["faint"])
    top = []
    x = x0
    if lname:
        top.append(f'<circle cx="{x + 5}" cy="34" r="5" fill="{lcol}"/>')
        top.append(f'<text class="m" x="{x + 16}" y="38" font-size="11.5" fill="{C["muted"]}">{esc(lname)}</text>')
        x += 16 + tw(lname, "mono", 11.5) + 16
    if r.get("stars"):
        top.append(f'<text class="m" x="{x}" y="38" font-size="11.5" fill="{C["muted"]}">{r["stars"]} {"star" if r["stars"] == 1 else "stars"}</text>')
    top.append(arrow(W - 32, 33, 10, C["muted"], 1.8))
    body.append(f'<g>{"".join(top)}</g>')
    body.append(f'<text class="s" x="{x0}" y="72" font-size="19" font-weight="600" letter-spacing="-.3" fill="{C["text"]}">'
                f'{esc(clip(r["title"], "sans600", 19, W - 2 * x0))}</text>')
    desc = wrap(r["description"], "sans400", 13.5, W - 2 * x0, 2) if r["description"] else []
    if desc:
        body.append(f'<text class="s" x="{x0}" y="98" font-size="13.5" fill="{C["body"]}">'
                    + "".join(f'<tspan x="{x0}" dy="{0 if k == 0 else 20}">{esc(d)}</tspan>' for k, d in enumerate(desc))
                    + "</text>")
    if r["stack"]:
        st = clip(" · ".join(r["stack"]), "mono", 11, W - 2 * x0)
        body.append(f'<text class="m" x="{x0}" y="{H - 24}" font-size="11" fill="{C["accent"]}" fill-opacity=".9">{esc(st)}</text>')
    inner = f'<g{anim("rise", .7, .3 + i * .12)}>{"".join(body)}</g>'
    label = f'{r["title"]}: {r["description"]}'
    return doc(W, H, inner, ["sans400", "sans600", "mono"], label)


# ----------------------------------------------------------------------------- README

def write(name, svg):
    with open(os.path.join(CARDS, name), "w", encoding="utf-8") as f:
        f.write(svg)


def main():
    os.makedirs(CARDS, exist_ok=True)
    data, days = load_days()
    s = stats(days, data.get("total"))
    links = CFG.get("links", {})
    site = links.get("site", "")

    start("hero")
    write("hero.svg", hero())
    parts = ["<!-- Generated by scripts/render_readme_cards.py. Edit config.json or readme_extra.md, not this file. -->",
             f'<a href="{site}"><img src="./cards/hero.svg" width="100%" alt="{esc(" ".join(CFG["name"]))}, {esc(CFG["role"])}" /></a>']

    if CFG.get("show_activity", True):
        start("graph")
        write("graph.svg", graph(data, days, s))
        start("activity")
        write("activity.svg", activity(s))
        parts.append(f'<img src="./cards/graph.svg" width="100%" alt="{s["total"]} contributions in the last year" />')
        parts.append(f'<img src="./cards/activity.svg" width="100%" alt="Monthly contributions and streaks" />')

    row = []
    start("tiles")
    for i, t in enumerate(CFG["tiles"][:3]):
        write(f"tile-{i + 1}.svg", tile(t, i))
        row.append(f'<a href="{esc(t["href"])}"><img src="./cards/tile-{i + 1}.svg" width="32.5%" '
                   f'alt="{esc(t["label"].title())}: {esc(str(t["value"]) + t.get("suffix", ""))} {esc(t["caption"])}" /></a>')
    parts.append("\n".join(row))

    repos = featured_repos()
    for old in os.listdir(CARDS):
        if old.startswith("repo-") and old.endswith(".svg"):
            os.remove(os.path.join(CARDS, old))
    rrow = []
    start("repos")
    for i, r in enumerate(repos):
        write(f"repo-{i + 1}.svg", repo_card(r, i))
        rrow.append(f'<a href="{esc(r.get("url", ""))}"><img src="./cards/repo-{i + 1}.svg" width="49.5%" alt="{esc(r["title"])}" /></a>')
    if rrow:
        parts.append("\n".join(rrow))

    foot = [f'<a href="{esc(u)}">{label}</a>' for key, label in
             (("site", "Portfolio"), ("linkedin", "LinkedIn"), ("resume", "Resume")) if (u := links.get(key))]
    if foot:
        parts.append('<p align="center">' + " · ".join(foot) + "</p>")

    extra = os.path.join(ROOT, "readme_extra.md")
    if os.path.exists(extra):
        with open(extra, encoding="utf-8") as f:
            parts.append(f.read().strip())

    with open(README, "w", encoding="utf-8") as f:
        f.write("\n\n".join(parts) + "\n")
    mode = "static" if STATIC else "animated"
    print(f"rendered {mode} cards: {s['total']} contributions, {len(repos)} repos -> {os.path.relpath(CARDS, ROOT)}/")


if __name__ == "__main__":
    main()
