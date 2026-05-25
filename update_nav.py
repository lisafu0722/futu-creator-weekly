"""Update hdr-week-nav across archived weekly reports to add W21 + properly archive W20."""
import os, re

ROOT = os.path.dirname(os.path.abspath(__file__))

OPTIONS_TEMPLATE = [
    ('index.html', '第21周（5/18–5/24）', 'W21'),
    ('weekly_report_2026W20_0511-0517.html', '第20周（5/11–5/17）', 'W20'),
    ('weekly_report_2026W19_0504-0510.html', '第19周（5/4–5/10）', 'W19'),
    ('weekly_report_2026W18_0427-0503.html', '第18周（4/27–5/3）', 'W18'),
    ('weekly_report_2026W17_0420-0426.html', '第17周（4/20–4/26）', 'W17'),
    ('weekly_report_2026W16_0413-0419.html', '第16周（4/13–4/19）', 'W16'),
    ('weekly_report_2026W15_0406-0412.html', '第15周（4/6–4/12）', 'W15'),
    ('weekly_report_2026W14.html', '第14周', 'W14'),
]

TARGETS = [
    ('weekly_report_2026W20_0511-0517.html', 'W20'),
    ('weekly_report_2026W19_0504-0510.html', 'W19'),
    ('weekly_report_2026W18_0427-0503.html', 'W18'),
    ('weekly_report_2026W17_0420-0426.html', 'W17'),
    ('weekly_report_2026W16_0413-0419.html', 'W16'),
    ('weekly_report_2026W15_0406-0412.html', 'W15'),
    ('weekly_report_2026W14.html', 'W14'),
]

def build_select(selected_tag):
    lines = []
    for href, label, tag in OPTIONS_TEMPLATE:
        sel = ' selected' if tag == selected_tag else ''
        lines.append(f'      <option value="{href}"{sel}>{label}</option>')
    return ('    <select onchange="if(this.value)location.href=this.value">\n'
            + '\n'.join(lines) + '\n    </select>')

sel_pat = re.compile(r'(<div class="hdr-week-nav">\s*<label>查看周报</label>\s*)<select[^>]*>.*?</select>', re.DOTALL)

for fname, sel_tag in TARGETS:
    path = os.path.join(ROOT, fname)
    if not os.path.exists(path):
        print(f'SKIP missing: {fname}'); continue
    src = open(path, encoding='utf-8').read()
    new_select = build_select(sel_tag)
    new_src, n = sel_pat.subn(lambda m: m.group(1) + new_select, src, count=1)
    if n == 0:
        print(f'WARN: pattern not matched in {fname}'); continue
    if new_src == src:
        print(f'NOOP: {fname}'); continue
    open(path, 'w', encoding='utf-8').write(new_src)
    print(f'updated: {fname} (selected={sel_tag})')
print('done')
