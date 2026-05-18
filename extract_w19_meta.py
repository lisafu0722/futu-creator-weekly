"""Extract creator metadata (fans, accttype, owner, nick, cert) from W19 HTML."""
import re, json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(ROOT, 'weekly_report_2026W19_0504-0510.html'), encoding='utf-8').read()

# Pattern for active creator cards
card_pat = re.compile(
    r'<div class="creator-card[^"]*"\s+data-uid="(\d+)"[^>]*?'
    r'data-fans="(\d+)"\s+data-accttype="([^"]+)"\s+data-owner="([^"]+)"[^>]*>'
    r'(.*?)</div>\s*(?=<div class="creator-card|\s*</div>\s*<!-- 未活跃)',
    re.DOTALL,
)

meta = {}
for m in card_pat.finditer(src):
    uid, fans, acct, owner, body = m.groups()
    # extract nick
    name_m = re.search(r'<a class="creator-name"[^>]*>([^<]+)</a>', body)
    nick = name_m.group(1) if name_m else ''
    cert_m = re.search(r'<span class="cert-badge">([^<]+)</span>', body)
    cert = cert_m.group(1) if cert_m else ''
    meta[uid] = {
        'fans': int(fans),
        'accttype': acct,
        'owner': owner,
        'nick': nick,
        'cert': cert,
    }

# Inactive chips
chip_pat = re.compile(
    r'<a class="inactive-chip" data-owner="([^"]+)" data-accttype="([^"]+)" '
    r'href="https://q\.futunn\.com/profile/(\d+)"[^>]*>([^<]+)</a>'
)
inactive = {}
inactive_sec = re.search(r'<!-- 未活跃 -->.*', src, re.DOTALL).group(0)
for m in chip_pat.finditer(inactive_sec):
    owner, acct, uid, nick = m.groups()
    inactive[uid] = {
        'fans': 0,  # unknown for inactive — fill 0 default
        'accttype': acct,
        'owner': owner,
        'nick': nick,
        'cert': '',
    }

# Merge: active meta overrides inactive
all_meta = {**inactive, **meta}
print(f'active meta: {len(meta)}, inactive meta: {len(inactive)}, total: {len(all_meta)}')

with open(os.path.join(ROOT, 'creator_meta.json'), 'w', encoding='utf-8') as f:
    json.dump(all_meta, f, indent=2, ensure_ascii=False)
print(f'saved creator_meta.json')
