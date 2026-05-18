"""Update hdr-week-nav in all archive HTML files to include W19 and W20."""
import re, os

ROOT = os.path.dirname(os.path.abspath(__file__))

# Canonical option list (current week first → newest, with selected applied per-file)
WEEKS = [
    ('index.html', '第20周（5/11–5/17）', 'W20'),
    ('weekly_report_2026W19_0504-0510.html', '第19周（5/4–5/10）', 'W19'),
    ('weekly_report_2026W18_0427-0503.html', '第18周（4/27–5/3）', 'W18'),
    ('weekly_report_2026W17_0420-0426.html', '第17周（4/20–4/26）', 'W17'),
    ('weekly_report_2026W16_0413-0419.html', '第16周（4/13–4/19）', 'W16'),
    ('weekly_report_2026W15_0406-0412.html', '第15周（4/6–4/12）', 'W15'),
    ('weekly_report_2026W14.html', '第14周', 'W14'),
]

# (file, week_id) for each archive's "self"
SELF = {
    'index.html': 'W20',
    'weekly_report_2026W19_0504-0510.html': 'W19',
    'weekly_report_2026W18_0427-0503.html': 'W18',
    'weekly_report_2026W17_0420-0426.html': 'W17',
    'weekly_report_2026W16_0413-0419.html': 'W16',
    'weekly_report_2026W15_0406-0412.html': 'W15',
    'weekly_report_2026W14.html': 'W14',
}

def build_options(self_week):
    out = []
    for href, label, wk in WEEKS:
        sel = ' selected' if wk == self_week else ''
        out.append(f'      <option value="{href}"{sel}>{label}</option>')
    return '\n'.join(out)

# Match the entire hdr-week-nav block with options inside select
NAV_RE = re.compile(r'(<select onchange="if\(this\.value\)location\.href=this\.value">)(.*?)(</select>)', re.DOTALL)

for fname, self_week in SELF.items():
    path = os.path.join(ROOT, fname)
    if not os.path.exists(path):
        print(f'SKIP missing: {fname}')
        continue
    with open(path, encoding='utf-8') as f:
        src = f.read()
    options_block = build_options(self_week)
    if 'hdr-week-nav' not in src:
        print(f'NO NAV: {fname} (skipping — needs manual addition)')
        continue
    new = NAV_RE.sub(lambda m: m.group(1) + '\n' + options_block + '\n    ' + m.group(3), src, count=1)
    if new == src:
        print(f'NO CHANGE: {fname}')
        continue
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new)
    print(f'UPDATED: {fname} (selected={self_week})')

print('\nNote: weekly_report_2026W18_0427-0503.html has NO hdr-week-nav and needs manual addition.')
