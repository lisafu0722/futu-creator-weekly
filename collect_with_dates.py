"""
动态日期版采集脚本 - 从环境变量读取日期范围
供 weekly_update.py 调用
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os, requests, json, time, re
from datetime import datetime, timezone, timedelta

# 从环境变量读取日期
TZ_HK = timezone(timedelta(hours=8))
start_str = os.environ.get('COLLECT_START_DATE', '2026-04-06')
end_str = os.environ.get('COLLECT_END_DATE', '2026-04-12')
start_date = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=TZ_HK)
end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=TZ_HK)
START_TS = int(start_date.timestamp())
END_TS = int(end_date.timestamp())

CREATOR_IDS = [
    11341665, 23462267, 17296331, 7223813, 1162342, 1132830, 28650147,
    11351602, 11891989, 16751620, 33748142, 15522366, 14405456, 18953260,
    18932740, 16565779, 25169348, 33984190, 1513002, 7275545, 17813031,
    11350158, 16459220, 13298710, 10203125, 13340775, 232846513, 27027219,
    33294691, 26056371, 23597001, 31386762, 23602671, 1160930, 18031209,
    16134209, 17491305, 11292105, 14657515, 124719, 17693722, 16564531,
    7971272, 5995073, 7625228, 7004578, 1409953, 25481759, 10200673,
    16712323, 18799623, 16891741, 7198520, 5950768, 11995189, 5579233,
    11364086, 11922518, 7493895, 12623418, 2838770, 1894219, 11283976,
    1472793, 26938318, 2854700, 12178975, 11884113, 1312525, 5961921,
    5478250, 29638625, 12257686, 7474530, 2869652, 14060116, 16637818,
    17981141, 7117423, 25484328, 10604518, 18218061, 5977079, 28841750,
    15389198, 30752545, 10219042, 31303717, 12089972, 1158281, 12313985,
    13503549, 11297920, 231866069, 2845719, 32607859, 27747031, 29747249,
    7926205, 30936527, 16428923, 15816956, 3351456, 25914640, 15765592,
    32754839, 7483116, 15822363, 18437538, 1240288, 1065155, 29558645,
    18641135, 11578390, 29817577, 7780146, 7149196, 7351896, 35153213,
    231491161, 26391646, 233869085, 13248499, 34275720, 33590692, 35339163,
    7045255, 21257693, 127715, 35244821, 33792705, 28424063, 28241713,
    31065447, 231575065, 34123772, 29795261, 12604240, 24989235, 7388642,
    17567706, 26294087, 5637519, 631978, 165850, 16997826, 35143402,
    231870570, 32861462, 12107698, 31505740, 1499823, 232418329, 18004503,
    11884979, 15813386, 5890381, 15584643, 232965591, 12778176, 28353219,
    234186329, 14639775, 231506941, 26621837, 34125173, 22059035, 30481835,
    3226989, 232787076, 12103405, 21036193, 2184566, 30385745, 5263553
]

FEED_TYPE_MAP = {
    1: '原创帖', 2: '转发帖', 3: '转发帖', 4: '文章', 5: '股票评论',
    6: '评论', 7: '文章', 8: '问答', 9: '视频', 10: '直播', 11: '投票',
}

script_dir = os.path.dirname(os.path.abspath(__file__))

def build_session():
    cookies_file = os.path.join(script_dir, 'cookies_final.json')
    with open(cookies_file, encoding='utf-8') as f:
        raw_cookies = json.load(f)
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    for c in raw_cookies:
        s.cookies.set(c['name'], c['value'], domain=c['domain'].lstrip('.'))
    return s

def extract_text(rich_text):
    if not rich_text:
        return ''
    parts = []
    for seg in rich_text:
        t = seg.get('type', 0)
        if t == 0:
            text = re.sub(r'<[^>]+>', ' ', seg.get('text', '')).strip()
            if text:
                parts.append(text)
        elif t == 1:
            nick = seg.get('user', {}).get('nick_name', '')
            if nick:
                parts.append(f'@{nick}')
        elif t == 2:
            topic = seg.get('topic', {}).get('name', '')
            if topic:
                parts.append(f'#{topic}#')
        elif t == 3:
            s = seg.get('stock', {})
            if s.get('stock_name'):
                parts.append(f'${s["stock_name"]}({s.get("display_symbol","")})$')
    return ' '.join(parts).strip()

def fetch_posts(session, uid, start_ts, end_ts, max_pages=30):
    posts = []
    more_mark = None
    page = 0
    done = False
    while not done and page < max_pages:
        params = {'type': 301, 'num': 20, 'load_list_type': 1, 'target_uid': uid, '_': int(time.time() * 1000)}
        if more_mark:
            params['more_mark'] = more_mark
        try:
            r = session.get('https://q.futunn.com/nnq/personal-list', params=params, timeout=15)
            data = r.json()
        except Exception as e:
            break
        feed = data.get('feed', [])
        if not feed:
            break
        page += 1
        for item in feed:
            common = item.get('common', {})
            ts = int(common.get('timestamp', 0))
            if ts == 0:
                continue
            if ts > end_ts:
                continue
            elif ts < start_ts:
                done = True
                break
            else:
                summary = item.get('summary', {})
                rich_text = summary.get('rich_text', [])
                text_content = extract_text(rich_text)
                feed_type_num = common.get('feed_type', 0)
                stocks = []
                for seg in rich_text:
                    if seg.get('type') == 3:
                        s = seg.get('stock', {})
                        if s.get('stock_name'):
                            stocks.append({'name': s['stock_name'], 'code': s.get('display_symbol', '')})
                dt = datetime.fromtimestamp(ts, tz=TZ_HK)
                posts.append({
                    'feed_id': common.get('feed_id', ''),
                    'timestamp': ts,
                    'date': dt.strftime('%Y-%m-%d'),
                    'datetime': dt.strftime('%Y-%m-%d %H:%M'),
                    'weekday': ['周一','周二','周三','周四','周五','周六','周日'][dt.weekday()],
                    'feed_type': feed_type_num,
                    'feed_type_str': FEED_TYPE_MAP.get(feed_type_num, f'类型{feed_type_num}'),
                    'title': common.get('feed_title', '') or '',
                    'text': text_content,
                    'word_count': common.get('word_count', 0),
                    'has_image': len(summary.get('picture_items', [])) > 0,
                    'image_count': len(summary.get('picture_items', [])),
                    'stocks_mentioned': stocks,
                    'likes': item.get('like', {}).get('liked_num', 0),
                    'comments': item.get('comment', {}).get('comment_count', 0),
                    'views': common.get('browse_count', 0),
                    'shares': common.get('share_count', 0),
                    'is_popular': common.get('is_popular', False),
                    'author_uid': str(item.get('user_info', {}).get('user_id', '')),
                })
        more_mark = data.get('more_mark', '')
        if not more_mark:
            done = True
        if not done:
            time.sleep(0.3)
    return posts

def get_nick_name(session, uid):
    try:
        import re as re2
        r = session.get(f'https://q.futunn.com/profile/{uid}', timeout=10)
        m = re2.search(r'<meta property="og:title" content="([^"]+)的个人主页', r.text)
        if m:
            return m.group(1)
    except:
        pass
    return f'用户{uid}'

def main():
    week_num = start_date.isocalendar()[1]
    year = start_date.year
    week_str = f'{year}W{week_num:02d}'

    print(f"采集 {start_str} - {end_str} 数据 (周 {week_str})")
    session = build_session()

    all_results = {}
    total_posts = 0

    for i, uid in enumerate(CREATOR_IDS):
        posts = fetch_posts(session, uid, START_TS, END_TS)
        total_posts += len(posts)

        nick = ''
        if posts:
            nick = posts[0].get('nick_name', '')
        if not nick:
            try:
                nick = get_nick_name(session, uid)
            except:
                nick = f'用户{uid}'

        active_days = sorted(set(p['date'] for p in posts))
        content_types = {}
        for p in posts:
            t = p['feed_type_str']
            content_types[t] = content_types.get(t, 0) + 1

        all_results[str(uid)] = {
            'uid': str(uid),
            'nick_name': nick,
            'week': f'{year}-W{week_num:02d}',
            'post_count': len(posts),
            'active_days': active_days,
            'active_day_count': len(active_days),
            'content_types': content_types,
            'total_likes': sum(p['likes'] for p in posts),
            'total_comments': sum(p['comments'] for p in posts),
            'total_views': sum(p['views'] for p in posts),
            'posts': posts,
        }

        if (i + 1) % 20 == 0:
            print(f"  进度: {i+1}/{len(CREATOR_IDS)}, 总帖子: {total_posts}")
        time.sleep(0.5)

    output = {
        'week': f'{year}-W{week_num:02d}',
        'start_date': start_str,
        'end_date': end_str,
        'total_creators': len(CREATOR_IDS),
        'active_creators': sum(1 for v in all_results.values() if v['post_count'] > 0),
        'total_posts': total_posts,
        'collected_at': datetime.now(TZ_HK).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'creators': all_results,
    }

    data_file = os.path.join(script_dir, f'week_data_{week_str}.json')
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # 同时更新最新数据文件（供 generate_report.py 使用）
    with open(os.path.join(script_dir, 'week_data_enriched.json'), 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"采集完成: {total_posts} 条帖子，活跃 {output['active_creators']} 人")
    print(f"数据保存: {data_file}")

if __name__ == '__main__':
    main()
