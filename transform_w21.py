"""Transform W21 collected schema -> build schema (matches w20_all177_data.json)."""
import json, os
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
src = json.load(open(os.path.join(ROOT, 'week_data_2026W21.json'), encoding='utf-8'))

W20 = json.load(open(os.path.join(ROOT, 'w20_priority26_data.json'), encoding='utf-8'))
PRIORITY_ORDER = W20['priority_uids_order']

creators_in = src['creators'] if 'creators' in src else src
out_creators = {}

for uid, c in creators_in.items():
    posts_out = []
    sum_b = sum_l = sum_cm = sum_sh = 0
    for p in c.get('posts', []):
        ts = p.get('timestamp', 0)
        stocks = []
        for s in p.get('stocks_mentioned') or []:
            if isinstance(s, dict):
                nm = s.get('name') or s.get('code')
                if nm: stocks.append(nm)
            elif isinstance(s, str):
                stocks.append(s)
        po = {
            'fid': str(p.get('feed_id') or ''),
            'ts': ts,
            'ftype': p.get('feed_type', 0),
            'title': p.get('title', '') or '',
            'browse': p.get('views', 0) or 0,
            'like': p.get('likes', 0) or 0,
            'comment': p.get('comments', 0) or 0,
            'share': p.get('shares', 0) or 0,
            'wc': p.get('word_count', 0) or 0,
            'stocks': stocks,
        }
        posts_out.append(po)
        sum_b += po['browse']; sum_l += po['like']; sum_cm += po['comment']; sum_sh += po['share']
    out_creators[uid] = {
        'uid': uid,
        'nick': c.get('nick_name', '') or '',
        'post_count': len(posts_out),
        'browse': sum_b,
        'like': sum_l,
        'comment': sum_cm,
        'share': sum_sh,
        'posts': posts_out,
    }

all_out = {
    'week': '2026W21',
    'start_date': '2026-05-18',
    'end_date': '2026-05-24',
    'collected_at': datetime.now().isoformat(timespec='seconds'),
    'total': len(out_creators),
    'creators': out_creators,
}
json.dump(all_out, open(os.path.join(ROOT, 'w21_all_data.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=2)
print(f'wrote w21_all_data.json: {len(out_creators)} creators')

priority_creators = {uid: out_creators[uid] for uid in PRIORITY_ORDER if uid in out_creators}
priority_out = {
    'week': '2026W21',
    'start_date': '2026-05-18',
    'end_date': '2026-05-24',
    'collected_at': all_out['collected_at'],
    'priority_uids_order': PRIORITY_ORDER,
    'creators': priority_creators,
}
json.dump(priority_out, open(os.path.join(ROOT, 'w21_priority26_data.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=2)
print(f'wrote w21_priority26_data.json: {len(priority_creators)} of {len(PRIORITY_ORDER)} priority')

missing = [u for u in PRIORITY_ORDER if u not in out_creators]
if missing: print(f'missing priority uids: {missing}')
inactive = [u for u in PRIORITY_ORDER if u in out_creators and out_creators[u]['post_count'] == 0]
if inactive: print(f'inactive priority uids: {inactive}')
