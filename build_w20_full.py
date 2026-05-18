"""
Build W20 index.html with full W19-style structure:
- Top overview (KPIs, owner table, content summary, top stocks, top posters)
- Top10 likes table
- Daily distribution chart (SVG)
- Full controls bar (search/sort/active-inactive tabs/account type/owner/lang)
- 175 creator cards: 26 priority with cs2 reflection blocks, rest simple
- Inactive chips section
- Footer + JS
"""
import json, os, html, re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
HK = timezone(timedelta(hours=8))

# ---------------- Load data ----------------
w20 = json.load(open(os.path.join(ROOT, 'w20_all177_data.json'), encoding='utf-8'))
w19 = json.load(open(os.path.join(ROOT, 'w19_all175_data.json'), encoding='utf-8'))
priority_data = json.load(open(os.path.join(ROOT, 'w20_priority26_data.json'), encoding='utf-8'))
meta = json.load(open(os.path.join(ROOT, 'creator_meta.json'), encoding='utf-8'))

PRIORITY_ORDER = priority_data['priority_uids_order']
PRIORITY_SET = set(PRIORITY_ORDER)

# Backfill missing meta for new priority creators
# Manual owner assignment for priority KOLs not in W19 175-meta
NEW_PRIORITY_OWNERS = {
    '7109550': 'blakeli',     # 趋势就要HODL住
    '12775482': 'blakeli',    # 潘老闲新增的时候
}
for uid in PRIORITY_ORDER:
    if uid not in meta:
        nick = priority_data['creators'].get(uid, {}).get('nick', '') or w20['creators'].get(uid, {}).get('nick', f'用户{uid}')
        owner = NEW_PRIORITY_OWNERS.get(uid, 'lisafu')
        meta[uid] = {'fans': 0, 'accttype': 'personal', 'owner': owner, 'nick': nick, 'cert': ''}

# ---------------- Constants ----------------
FTYPE_MAP = {1:'原创帖',2:'转发帖',3:'转发帖',4:'文章',5:'股票评论',6:'评论',7:'文章',8:'问答',9:'视频',10:'直播',11:'投票'}
WEEKDAYS = ['周一','周二','周三','周四','周五','周六','周日']
WEEK_DATES = ['2026-05-11','2026-05-12','2026-05-13','2026-05-14','2026-05-15','2026-05-16','2026-05-17']
WEEK_DATE_LABELS = ['5/11(一)','5/12(二)','5/13(三)','5/14(四)','5/15(五)','5/16(六)','5/17(日)']

# ---------------- Helpers ----------------
def esc(s): return html.escape(str(s) if s is not None else '', quote=True)

def fmt_int(n):
    try: n=int(n or 0)
    except: n=0
    return f'{n:,}'

def fmt_wan(n):
    n = int(n or 0)
    if n >= 100_000_000:
        return f'{n/100_000_000:.1f}亿'.replace('.0亿','亿')
    if n >= 10_000:
        return f'{n/10_000:.1f}万'.replace('.0万','万')
    return f'{n:,}'

def feed_url(fid): return f'https://q.futunn.com/feed/{fid}'

def stock_search_url(name):
    return f'https://www.futunn.com/quote/search?keyword={name}'

def date_from_ts(ts):
    return datetime.fromtimestamp(int(ts), tz=HK)

def short_title(t, n=24):
    if not t: return '（无标题）'
    return t if len(t) <= n else t[:n-1] + '…'

# ---------------- Aggregate stats ----------------
total_creators = len(w20['creators'])
active = [c for c in w20['creators'].values() if c.get('post_count',0)>0]
inactive_uids = [uid for uid,c in w20['creators'].items() if c.get('post_count',0)==0]
active_count = len(active)
inactive_count = len(inactive_uids)
active_rate = round(active_count*100/total_creators)

# Personal vs media post counts (only personal accounts for "总原创内容" per W19 footnote)
personal_post_count = sum(c['post_count'] for uid,c in w20['creators'].items()
                          if meta.get(uid,{}).get('accttype','personal')=='personal')
total_views_all = sum(c['browse'] for c in w20['creators'].values())
total_likes_all = sum(c['like'] for c in w20['creators'].values())
total_comments_all = sum(c['comment'] for c in w20['creators'].values())
avg_articles = round(personal_post_count / max(active_count,1), 1)

# Owner table
owners = ['blakeli','chuiszewu','kristrawzeng','lisafu']
owner_stats = {}
for o in owners:
    creators_o = [(uid,c) for uid,c in w20['creators'].items() if meta.get(uid,{}).get('owner')==o]
    total = len(creators_o)
    active_o = [c for uid,c in creators_o if c['post_count']>0]
    inactive_o = total - len(active_o)
    posts_total = sum(c['post_count'] for uid,c in creators_o)
    posts_personal = sum(c['post_count'] for uid,c in creators_o if meta.get(uid,{}).get('accttype')=='personal')
    posts_media = sum(c['post_count'] for uid,c in creators_o if meta.get(uid,{}).get('accttype')=='media')
    views_total = sum(c['browse'] for uid,c in creators_o)
    likes_total = sum(c['like'] for uid,c in creators_o)
    comments_total = sum(c['comment'] for uid,c in creators_o)
    rate = round(len(active_o)*100/max(total,1))
    owner_stats[o] = dict(total=total, active=len(active_o), inactive=inactive_o, rate=rate,
                          posts=posts_total, personal=posts_personal, media=posts_media,
                          views=views_total, likes=likes_total, comments=comments_total)

# Top stocks across all posts
stock_count = Counter()
for c in w20['creators'].values():
    seen = set()
    for p in c.get('posts',[]):
        for s in p.get('stocks',[]):
            if s and s not in seen:
                stock_count[s] += 1
                seen.add(s)

top_stocks = stock_count.most_common(10)

# Top posters (personal accounts only)
top_posters_data = []
for uid,c in w20['creators'].items():
    if meta.get(uid,{}).get('accttype')=='personal' and c['post_count']>0:
        top_posters_data.append((uid, c['nick'], c['post_count'], c['browse']))
top_posters_data.sort(key=lambda x: (-x[2], -x[3]))
top_posters = top_posters_data[:10]

# Highest-browse single creator
hi_browse_creator = max(active, key=lambda c: c['browse']) if active else None

# Top 10 likes posts
all_posts_flat = []
for uid,c in w20['creators'].items():
    for p in c.get('posts',[]):
        pp = dict(p)
        pp['uid'] = uid
        pp['nick'] = c['nick']
        all_posts_flat.append(pp)
all_posts_flat.sort(key=lambda p: (-p.get('like',0), -p.get('browse',0)))
top10_likes = all_posts_flat[:10]

# Daily distribution
daily_counts = [0]*7
for uid,c in w20['creators'].items():
    if meta.get(uid,{}).get('accttype')!='personal': continue  # personal only per W19
    for p in c.get('posts',[]):
        d = date_from_ts(p['ts']).strftime('%Y-%m-%d')
        if d in WEEK_DATES:
            daily_counts[WEEK_DATES.index(d)] += 1

# ---------------- CSS from W19 ----------------
w19_html = open(os.path.join(ROOT, 'weekly_report_2026W19_0504-0510.html'), encoding='utf-8').read()
css_block = w19_html[w19_html.index('<style>'):w19_html.index('</style>')+8]

# ---------------- Header ----------------
header_block = f'''<!-- 顶部标题 -->
<div class="hdr">
  <div class="hdr-badge">WEEK 20 · 2026</div>
  <h1>🐂 富途牛牛圈 创作者运营周报</h1>
  <div class="sub">2026 年第 20 周 &nbsp;·&nbsp; 5月11日（周一）— 5月17日（周日）</div>
  <div class="meta">数据采集于 2026-05-18 UTC+08:00 &nbsp;·&nbsp; 共纳入 {total_creators} 位创作者 &nbsp;·&nbsp; 26 位优先 KOL 含 cs2 反馈卡片</div>
  <div class="hdr-week-nav">
    <label>查看周报</label>
    <select onchange="if(this.value)location.href=this.value">
      <option value="index.html" selected>第20周（5/11–5/17）</option>
      <option value="weekly_report_2026W19_0504-0510.html">第19周（5/4–5/10）</option>
      <option value="weekly_report_2026W18_0427-0503.html">第18周（4/27–5/3）</option>
      <option value="weekly_report_2026W17_0420-0426.html">第17周（4/20–4/26）</option>
      <option value="weekly_report_2026W16_0413-0419.html">第16周（4/13–4/19）</option>
      <option value="weekly_report_2026W15_0406-0412.html">第15周（4/6–4/12）</option>
      <option value="weekly_report_2026W14.html">第14周</option>
    </select>
  </div>
</div>
'''

# ---------------- Overview KPI ----------------
kpi_block = f'''<!-- 本周总结 -->
<div class="overview-box">
  <h2>本周总结 <span style="font-size:13px;font-weight:normal;color:#888;">（发帖量仅统计个人号，其他统计个人号+媒体号）</span></h2>
  <div class="overview-p">
<div class="ov-kpi-row">
  <div class="ov-kpi-group">
    <div class="ov-kpi-label">创作者活跃</div>
    <div class="ov-kpi-pair">
      <div class="ov-kpi"><div class="ov-kpi-n">{active_count}<span class="ov-kpi-u">/{total_creators}</span></div><div class="ov-kpi-l">活跃创作者</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{active_rate}<span class="ov-kpi-u">%</span></div><div class="ov-kpi-l">活跃率</div></div>
      <div class="ov-kpi ov-kpi-dim"><div class="ov-kpi-n">{inactive_count}</div><div class="ov-kpi-l">未活跃</div></div>
    </div>
    <div class="ov-footnote">活跃指本周有发布原创内容</div>
  </div>
  <div class="ov-kpi-divider"></div>
  <div class="ov-kpi-group">
    <div class="ov-kpi-label">内容数据</div>
    <div class="ov-kpi-pair">
      <div class="ov-kpi"><div class="ov-kpi-n">{personal_post_count:,}</div><div class="ov-kpi-l">总原创内容数量</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{fmt_wan(total_views_all)}</div><div class="ov-kpi-l">总浏览量</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{total_likes_all:,}</div><div class="ov-kpi-l">点赞</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{total_comments_all:,}</div><div class="ov-kpi-l">评论</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{avg_articles}</div><div class="ov-kpi-l">均文章数</div></div>
    </div>
  </div>
</div>
'''

# Owner table
def owner_row(o):
    s = owner_stats[o]
    return f'''    <tr>
      <td class="ov-ot-name">{o}</td>
      <td>{s['total']}</td>
      <td><span class="ov-owner-active">{s['active']}</span></td>
      <td><span class="ov-owner-inactive">{s['inactive']}</span></td>
      <td>
        <div class="ov-ot-bar-wrap">
          <div class="ov-ot-bar"><div class="ov-ot-bar-fill" style="width:{s['rate']}%"></div></div>
          <span class="ov-ot-rate">{s['rate']}%</span>
        </div>
      </td>
      <td class="ov-ot-num">{s['posts']:,}</td>
      <td class="ov-ot-num ov-ot-sub">{s['personal']}</td>
      <td class="ov-ot-num ov-ot-sub">{s['media']}</td>
      <td class="ov-ot-num">{fmt_wan(s['views'])}</td>
      <td class="ov-ot-num">{s['likes']:,}</td>
      <td class="ov-ot-num">{s['comments']:,}</td>
    </tr>'''

owner_table = f'''<div class="ov-owner-table-wrap">
  <div class="ov-owner-label">跟进人分布</div>
  <table class="ov-owner-table">
    <thead><tr>
      <th>跟进人</th><th>总人数</th><th>活跃</th><th>未发布</th><th>活跃率</th>
      <th>发帖</th><th>个人号</th><th>媒体号</th><th>浏览</th><th>点赞</th><th>评论</th>
    </tr></thead>
    <tbody>
{chr(10).join(owner_row(o) for o in owners)}
    </tbody>
  </table>
</div>
'''

# ---------------- Detail row (content summary + top stocks + top posters) ----------------
content_summary = '''<div class="ov-panel">
    <div class="ov-panel-title">📝 本周内容总结</div>
    <div class="ov-item ov-item-note"><span class="ov-icon">💡</span><span class="ov-item-note-text">本周市场聚焦中美元首会面、美联储新主席换届预期、半导体板块连涨后回调与AI叙事二度发酵。港股恒指在25700–26200区间震荡，关注科网及券商板块；港股IPO周热度集中在拓璞、驭势科技、丹诺医药等新股。美股关注科技板块波动与黄金/美债避险表现，加密市场围绕比特币9.5万关口与稳定币立法推进。</span></div>
    <div class="ov-topic-row">
      <div class="ov-topic-label">热议话题</div>
      <div class="ov-topic-tags"><span class="topic-tag">中美元首会面</span><span class="topic-tag">美联储换届预期</span><span class="topic-tag">半导体回调</span><span class="topic-tag">港股IPO周</span><span class="topic-tag">AI二次叙事</span><span class="topic-tag">比特币9.5万</span><span class="topic-tag">黄金避险</span></div>
    </div>
  </div>'''

# Top stocks
def stock_url_for(name):
    # Heuristic mapping for common names
    map_u = {
        '騰訊控股':'https://www.futunn.com/stock/00700-HK',
        '腾讯控股':'https://www.futunn.com/stock/00700-HK',
        '阿里巴巴':'https://www.futunn.com/stock/09988-HK',
        '阿里巴巴-W':'https://www.futunn.com/stock/09988-HK',
        '美團':'https://www.futunn.com/stock/03690-HK',
        '美團-W':'https://www.futunn.com/stock/03690-HK',
        '小米集团':'https://www.futunn.com/stock/01810-HK',
        '小米集團':'https://www.futunn.com/stock/01810-HK',
        '小米集團-W':'https://www.futunn.com/stock/01810-HK',
        '中芯國際':'https://www.futunn.com/stock/00981-HK',
        '中芯国际':'https://www.futunn.com/stock/00981-HK',
        '英偉達':'https://www.futunn.com/stock/NVDA-US',
        '英伟达':'https://www.futunn.com/stock/NVDA-US',
        '特斯拉':'https://www.futunn.com/stock/TSLA-US',
        '比特币':'https://www.futunn.com/stock/BTC.CC-US',
        '比特幣':'https://www.futunn.com/stock/BTC.CC-US',
        '恒生指数':'https://www.futunn.com/index/800000-HK',
        '恒生指數':'https://www.futunn.com/index/800000-HK',
        '恒生科技指数':'https://www.futunn.com/index/HSTECH-HK',
        '恒生科技指數':'https://www.futunn.com/index/HSTECH-HK',
        '纳斯达克综合指数':'https://www.futunn.com/index/.IXIC-US',
        '納斯達克綜合指數':'https://www.futunn.com/index/.IXIC-US',
        '标普500指数':'https://www.futunn.com/index/.SPX-US',
        '標普500指數':'https://www.futunn.com/index/.SPX-US',
    }
    return map_u.get(name, stock_search_url(name))

def medal(rank):
    if rank==1: return '🥇'
    if rank==2: return '🥈'
    if rank==3: return '🥉'
    return f'<span class="ov-rank">{rank}</span>'

stocks_panel_rows = []
for i,(name,cnt) in enumerate(top_stocks, 1):
    stocks_panel_rows.append(
        f'<div class="ov-rank-row"><span class="ov-medal">{medal(i)}</span>'
        f'<a class="ov-rank-name" href="{stock_url_for(name)}" target="_blank">{esc(name)}</a>'
        f'<span class="ov-rank-val">{cnt} 次</span></div>'
    )
stocks_panel = f'''<div class="ov-panel">
    <div class="ov-panel-title">🔥 热门标的 Top 10</div>
    {''.join(stocks_panel_rows)}
  </div>'''

# Top posters
posters_rows = []
for i,(uid,nick,pc,brw) in enumerate(top_posters, 1):
    posters_rows.append(
        f'<div class="ov-rank-row"><span class="ov-medal">{medal(i)}</span>'
        f'<a class="ov-rank-name" href="https://q.futunn.com/profile/{uid}" target="_blank">{esc(nick)}</a>'
        f'<span class="ov-rank-val">{pc}篇</span>'
        f'<span class="ov-rank-sub">{fmt_wan(brw)}浏览</span></div>'
    )

hi_browse_html = ''
if hi_browse_creator:
    # Find the personal account with highest browse
    pers_active = [c for uid,c in w20['creators'].items()
                   if meta.get(uid,{}).get('accttype')=='personal' and c['post_count']>0]
    if pers_active:
        hb = max(pers_active, key=lambda c: c['browse'])
        hi_browse_html = (
            f'<div class="ov-item ov-item-extra"><span class="ov-icon">👁</span>'
            f'<span class="ov-item-l">最高浏览</span>'
            f'<a class="ov-item-link" href="https://q.futunn.com/profile/{hb["uid"]}" target="_blank">{esc(hb["nick"])}</a>'
            f'<span class="ov-item-v">&nbsp;{fmt_wan(hb["browse"])}次</span></div>'
        )

posters_panel = f'''<div class="ov-panel">
    <div class="ov-panel-title">⭐ 发帖量 Top 10</div>
    {''.join(posters_rows)}
    <div class="ov-rank-divider"></div>
    {hi_browse_html}
    <div class="ov-footnote">仅展示个人号，不包含媒体号</div>
  </div>'''

detail_row = f'''<div class="ov-detail-row">
  {content_summary}
  {stocks_panel}
  {posters_panel}
</div></div>
</div>
'''

# ---------------- Top10 likes table ----------------
top10_rows = []
for i,p in enumerate(top10_likes, 1):
    rank = '🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else f'<b>{i}</b>'
    stocks_html = '<span style="color:var(--lt)">—</span>'
    if p.get('stocks'):
        stocks_html = ' '.join(
            f'<a class="tp-stock" href="{stock_url_for(s)}" target="_blank">{esc(s)}</a>'
            for s in p['stocks'][:3]
        )
    top10_rows.append(f'''<tr>
  <td class="tl-rank">{rank}</td>
  <td><a href="https://q.futunn.com/profile/{p["uid"]}" target="_blank" class="tl-author">{esc(p["nick"])}</a></td>
  <td><a href="{feed_url(p["fid"])}" target="_blank" class="tl-content">{esc(p.get("title") or "（无标题）")}</a></td>
  <td class="tl-stocks-cell">{stocks_html}</td>
  <td class="tl-num">{fmt_int(p["browse"])}</td>
  <td class="tl-num tl-likes">{p["like"]}</td>
  <td class="tl-num">{p["comment"]}</td>
  <td class="tl-num">{p["share"]}</td>
</tr>''')

top10_block = f'''<!-- 点赞量 Top10 -->
<div class="top5-sec">
  <h3>👍 点赞量 Top 10</h3>
  <table>
    <thead><tr>
      <th style="width:44px">排名</th>
      <th style="width:100px">作者</th>
      <th>内容</th>
      <th style="width:200px">关联标的</th>
      <th style="width:72px;text-align:right">浏览量</th>
      <th style="width:54px;text-align:right">点赞</th>
      <th style="width:54px;text-align:right">评论</th>
      <th style="width:54px;text-align:right">转发</th>
    </tr></thead>
    <tbody>{''.join(top10_rows)}</tbody>
  </table>
</div>
'''

# ---------------- Daily chart SVG ----------------
mx = max(daily_counts) if daily_counts else 1
def y_for(v):
    if mx == 0: return 112.0
    return 20.0 + (mx - v) / mx * 92.0
xs = [36.0 + i*107.33 for i in range(7)]

# Polygon points (filled area)
poly_pts = [f'{xs[0]:.1f},112']
for i,v in enumerate(daily_counts):
    poly_pts.append(f'{xs[i]:.1f},{y_for(v):.1f}')
poly_pts.append(f'{xs[-1]:.1f},112')
polyline_pts = ' '.join(f'{xs[i]:.1f},{y_for(v):.1f}' for i,v in enumerate(daily_counts))

dots = ''
for i,v in enumerate(daily_counts):
    is_weekend = i >= 5
    color = '#94a3b8' if is_weekend else '#FF6900'
    text_color = '#94a3b8' if is_weekend else '#0f172a'
    dots += (f'<circle cx="{xs[i]:.1f}" cy="{y_for(v):.1f}" r="5" fill="{color}" stroke="#fff" stroke-width="2"/>'
             f'<text x="{xs[i]:.1f}" y="{y_for(v)-10:.1f}" text-anchor="middle" font-size="11" fill="{text_color}" font-weight="700" font-family="PingFang SC,Microsoft YaHei,sans-serif">{v}</text>')
labels = ''
for i,lab in enumerate(WEEK_DATE_LABELS):
    is_weekend = i >= 5
    color = '#94a3b8' if is_weekend else '#64748b'
    labels += f'<text x="{xs[i]:.1f}" y="140.0" text-anchor="middle" font-size="11" fill="{color}" font-family="PingFang SC,Microsoft YaHei,sans-serif">{lab}</text>'

half_label = round(mx/2) if mx else 0
chart_block = f'''<!-- 每日分布图 -->
<div class="chart-sec" style="padding:18px 24px;">
  <h3>📅 每日发帖分布</h3>
  <div class="chart-wrap"><svg viewBox="0 0 700 140" width="100%" style="display:block;max-width:700px;margin:0 auto;">
  <defs>
    <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FF6900" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#FF6900" stop-opacity="0.01"/>
    </linearGradient>
  </defs>
  <line x1="36" y1="112.0" x2="680" y2="112.0" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4,3"/><text x="30" y="116.0" text-anchor="end" font-size="10" fill="#94a3b8" font-family="PingFang SC,Microsoft YaHei,sans-serif">0</text><line x1="36" y1="66.0" x2="680" y2="66.0" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4,3"/><text x="30" y="70.0" text-anchor="end" font-size="10" fill="#94a3b8" font-family="PingFang SC,Microsoft YaHei,sans-serif">{half_label}</text><line x1="36" y1="20.0" x2="680" y2="20.0" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4,3"/><text x="30" y="24.0" text-anchor="end" font-size="10" fill="#94a3b8" font-family="PingFang SC,Microsoft YaHei,sans-serif">{mx}</text>
  <polygon points="{' '.join(poly_pts)}" fill="url(#chartFill)"/>
  <polyline points="{polyline_pts}" fill="none" stroke="#FF6900" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  {dots}
  {labels}
</svg></div>
</div>
'''

# ---------------- Controls ----------------
ctrl_block = f'''<!-- 控制栏 -->
<div class="ctrl">
  <div class="search-wrap">
    <input type="text" id="si" placeholder="搜索创作者名称或 ID（支持简繁体）…" oninput="filter()">
    <button class="search-clear" id="sc" onclick="clearSearch()" title="清除搜索">✕</button>
  </div>
  <select id="ss" onchange="resort()">
    <option value="posts">按发帖数排序</option>
    <option value="views">按浏览量排序</option>
    <option value="likes">按点赞数排序</option>
    <option value="days">按活跃天数排序</option>
    <option value="fans">按粉丝数排序</option>
  </select>
  <div class="tabs">
    <button class="tab on" onclick="setTab('active',this)">活跃 ({active_count})</button>
    <button class="tab" onclick="setTab('inactive',this)">未发布 ({inactive_count})</button>
    <button class="tab" onclick="setTab('all',this)">全部</button>
  </div>
  <div class="tabs">
    <button class="tab on" onclick="setType('all',this)">全部账号</button>
    <button class="tab" onclick="setType('personal',this)">个人号</button>
    <button class="tab" onclick="setType('media',this)">媒体号</button>
  </div>
  <div class="tabs">
    <button class="tab on" onclick="setOwner('all',this)">全部跟进人</button>
    <button class="tab" onclick="setOwner('blakeli',this)">blakeli</button>
    <button class="tab" onclick="setOwner('chuiszewu',this)">chuiszewu</button>
    <button class="tab" onclick="setOwner('kristrawzeng',this)">kristrawzeng</button>
    <button class="tab" onclick="setOwner('lisafu',this)">lisafu</button>
    <span style="display:inline-block;width:1px;height:20px;background:var(--bdr);margin:0 4px;vertical-align:middle;"></span>
    <button class="tab on" onclick="setKol('all',this)">是否发送KOL周报：全部</button>
    <button class="tab" onclick="setKol('yes',this)">是</button>
    <button class="tab" onclick="setKol('no',this)">否</button>
  </div>
  <div class="tabs lang-tabs" data-lang-nav>
    <button type="button" class="tab on" data-lang="orig">原文</button>
    <button type="button" class="tab" data-lang="s">简体</button>
    <button type="button" class="tab" data-lang="t">繁體</button>
  </div>
  <span class="cnt-lbl" id="cl">显示 {active_count} 位</span>
</div>
'''

# ---------------- Card generators ----------------
def post_row_html(p):
    title = p.get('title') or '（无标题）'
    ftype = FTYPE_MAP.get(p.get('ftype',0), f"类型{p.get('ftype',0)}")
    dt = date_from_ts(p['ts'])
    wd = WEEKDAYS[dt.weekday()]
    img_marker = '📷' if p.get('has_image') else ''
    return f'''<div class="post-row">
  <span class="post-meta">
    <span class="post-date" style="color:#e74c3c">{dt.strftime("%Y-%m-%d %H:%M")} {wd}</span>
    <span class="badge">{ftype}</span>{img_marker}
  </span>
  <a class="post-link" href="{feed_url(p["fid"])}" target="_blank">{esc(title)}</a>
  <span class="post-metrics">👁{fmt_int(p.get("browse",0))} &nbsp;👍{fmt_int(p.get("like",0))} &nbsp;💬{fmt_int(p.get("comment",0))} &nbsp;🔁{fmt_int(p.get("share",0))}</span>
</div>'''

def stocks_row_html(posts):
    seen = []
    for p in posts:
        for s in p.get('stocks',[]) or []:
            if s and s not in seen:
                seen.append(s)
    if not seen: return ''
    chips = ''.join(
        f'<a class="stock-tag" href="{stock_url_for(s)}" target="_blank">{esc(s)}</a>'
        for s in seen[:8]
    )
    return f'<div class="stocks-row">关注标的：{chips}</div>'

def gen_simple_summary(c, m):
    """Plain summary line for non-priority active cards."""
    posts = c.get('posts',[])
    pc = c['post_count']
    if pc == 0:
        return ''
    sorted_p = sorted(posts, key=lambda p: -p.get('browse',0))
    top = sorted_p[0]
    titles_short = '、'.join(f'《{esc(short_title(p.get("title",""),18))}》' for p in posts[:4])
    types_count = Counter(FTYPE_MAP.get(p.get('ftype',0),'其他') for p in posts)
    types_summary = '、'.join(f'{t}{n}' for t,n in types_count.most_common(3))
    return (f'本周共发布 {pc} 篇内容（{types_summary}）。'
            f'最高互动：《{esc(short_title(top.get("title",""),22))}》（浏览 {fmt_int(top["browse"])}、获赞 {top["like"]}）。'
            f'累计浏览 {fmt_wan(c["browse"])}，获赞 {c["like"]}，评论 {c["comment"]}。')

def gen_card_simple(uid, c, m):
    posts = c.get('posts', [])
    pc = c['post_count']
    days = sorted({date_from_ts(p['ts']).strftime('%Y-%m-%d') for p in posts})
    day_count = len(days)
    fans = m.get('fans',0)
    nick = c.get('nick') or m.get('nick') or f'用户{uid}'
    accttype = m.get('accttype','personal')
    owner = m.get('owner','lisafu')
    cert = m.get('cert','')
    tier = 'tier-hi' if c['browse']>=1_000_000 else 'tier-mid' if c['browse']>=100_000 else 'tier-lo'
    eng = c['like'] + c['comment']*5 + c['share']*10
    fans_inline = f'👥 {fans:,}' if fans else '👥 —'
    cert_html = f'<span class="cert-badge">{esc(cert)}</span>' if cert else ''
    search = esc(nick.lower())

    # Posts list (simple - up to 20 visible by default with "more" hint)
    sorted_p = sorted(posts, key=lambda p:-p.get('ts',0))
    visible_posts = sorted_p[:20]
    more_count = len(sorted_p) - len(visible_posts)
    posts_html = ''.join(post_row_html(p) for p in visible_posts)
    if more_count > 0:
        posts_html += f'<div class="more-hint">…还有 {more_count} 条帖子</div>'

    summary = gen_simple_summary(c, m)
    stocks_row = stocks_row_html(posts)

    return f'''<div class="creator-card {tier}" data-uid="{uid}" data-posts="{pc}" data-views="{c['browse']}" data-likes="{c['like']}" data-days="{day_count}" data-engagement="{eng}" data-fans="{fans}" data-accttype="{accttype}" data-owner="{owner}" data-kol="no" data-search="{search}">
  <div class="card-header">
    <div class="name-row">
      <a class="creator-name" href="https://q.futunn.com/profile/{uid}" target="_blank">{esc(nick)}</a>
      <span class="creator-uid">#{uid}</span>
      <span class="owner-tag">{owner}</span>
      <span class="fans-inline">{fans_inline}</span>
      {cert_html}
    </div>
    <div class="active-days-line">本周活跃 <b>{day_count}/7</b> 天</div>
  </div>
  <div class="card-data-section">
    <div class="card-data-label">本周内容</div>
    <div class="metrics-row">
      <div class="metric"><span class="num">{pc}</span><span class="lbl">原创内容</span></div>
    </div>
  </div>
  <div class="card-data-section">
    <div class="card-data-label">互动数据</div>
    <div class="metrics-row">
      <div class="metric"><span class="num">{fmt_int(c["browse"])}</span><span class="lbl">浏览</span></div>
      <div class="metric"><span class="num">{fmt_int(c["like"])}</span><span class="lbl">获赞</span></div>
      <div class="metric"><span class="num">{fmt_int(c["comment"])}</span><span class="lbl">评论</span></div>
      <div class="metric"><span class="num">{fmt_int(c["share"])}</span><span class="lbl">被转发</span></div>
    </div>
  </div>
  <div class="creator-summary">{summary}</div>
  {stocks_row}
  <details class="posts-detail">
    <summary>📋 查看全部帖子（{pc} 条）</summary>
    <div class="posts-list">{posts_html or '<div class="more-hint">本周无内容</div>'}</div>
  </details>
</div>'''


# ---------------- Improved cs2 narrative for priority creators ----------------
def find_distinct_strength(posts):
    """Detect dominant content theme/style for tailored advice."""
    titles = [p.get('title','') for p in posts]
    types = Counter(FTYPE_MAP.get(p.get('ftype',0),'其他') for p in posts)
    avg_wc = sum(p.get('wc',0) for p in posts) / max(len(posts),1)
    has_long = any(p.get('wc',0) >= 1500 for p in posts)
    has_short = any(p.get('wc',0) > 0 and p.get('wc',0) < 200 for p in posts)
    return {
        'main_type': types.most_common(1)[0][0] if types else '',
        'avg_wc': avg_wc,
        'has_long': has_long,
        'has_short': has_short,
        'type_count': dict(types),
    }

def gen_cs2_insights(uid, c, m):
    """Generate richer cs2 reflection blocks."""
    posts = c.get('posts',[])
    pc = c['post_count']
    nick = c.get('nick') or m.get('nick') or f'用户{uid}'

    # Zero-post case
    if pc == 0:
        # Check W19 stats for comparison
        w19_c = w19['creators'].get(uid, {})
        w19_pc = len(w19_c.get('posts', []))
        w19_views = sum(p.get('views',0) for p in w19_c.get('posts',[]))
        had_w19 = w19_pc > 0
        if had_w19:
            hint = (f'对比上周（W19）您发布了 <em>{w19_pc}</em> 篇文章 / <em>{fmt_wan(w19_views)}</em> 浏览，'
                    f'本周完全断更，<b>读者订阅曲线和平台权重都会受影响</b>。建议尽快了解断更原因（休假 / 选题枯竭 / 时间冲突？）')
        else:
            hint = '上周也未发布，<b>账号已连续两周静默</b>，建议主动沟通是否仍有继续创作的意愿。'

        topics = '中美元首会面 / 美联储换届预期 / 半导体回调 / 港股新股周（拓璞、驭势、丹诺医药）/ AI二次叙事'
        return f'''
      <div class="cs2-insight">
        <div class="cs2-insight-h">📭 本周状态</div>
        <div class="cs2-insight-b">本周（5/11–5/17）<b>暂无原创内容发布</b>。{hint}</div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">💡 可主动提供的支持</div>
        <div class="cs2-insight-b">
          <ul>
            <li>分享本周市场热点作为选题切入点：{topics}</li>
            <li>询问是否需要素材支持（财报 / 公告 / 行情数据）或推荐位资源</li>
            <li>了解是否有未发布草稿，可协助安排发布节奏</li>
            <li>若长期无更新意愿，建议考虑在跟进列表中调整优先级</li>
          </ul>
        </div>
      </div>'''

    # ----- Active KOL -----
    sorted_by_browse = sorted(posts, key=lambda p:-p.get('browse',0))
    sorted_by_like = sorted(posts, key=lambda p:-p.get('like',0))
    sorted_by_share = sorted(posts, key=lambda p:-p.get('share',0))
    sorted_by_comment = sorted(posts, key=lambda p:-p.get('comment',0))
    top_browse = sorted_by_browse[0]
    top_like = sorted_by_like[0]
    top_share = sorted_by_share[0]

    # Day pattern
    days = sorted({date_from_ts(p['ts']).strftime('%Y-%m-%d') for p in posts})
    day_count = len(days)
    weekdays_set = sorted({date_from_ts(p['ts']).weekday() for p in posts})
    has_weekend = any(d>=5 for d in weekdays_set)
    times = sorted([date_from_ts(p['ts']).strftime('%H:%M') for p in posts])
    time_range = f'{times[0]}–{times[-1]}' if times else '—'
    # Time clustering
    hours = [date_from_ts(p['ts']).hour for p in posts]
    hr_counter = Counter(hours)
    common_hr = hr_counter.most_common(1)[0][0] if hr_counter else 0
    morning = sum(1 for h in hours if 6<=h<12)
    afternoon = sum(1 for h in hours if 12<=h<18)
    evening = sum(1 for h in hours if 18<=h<24)
    night = sum(1 for h in hours if 0<=h<6)
    period_parts = []
    for label, n in [('上午',morning),('下午',afternoon),('晚间',evening),('深夜',night)]:
        if n>0: period_parts.append(f'{label}{n}')
    period_str = '、'.join(period_parts)

    # Content type spread
    types = Counter(FTYPE_MAP.get(p.get('ftype',0),'其他') for p in posts)
    type_summary = '、'.join(f'{t} {n}' for t,n in types.most_common(3))
    avg_wc = round(sum(p.get('wc',0) for p in posts) / max(pc,1))

    # Engagement metrics
    eng_rate = (c['like']+c['comment']+c['share']) / max(c['browse'],1) * 100
    avg_browse = c['browse'] // max(pc,1)
    like_per_post = c['like'] / max(pc,1)
    share_per_post = c['share'] / max(pc,1)

    # Stocks
    stock_set = []
    for p in posts:
        for s in p.get('stocks',[]) or []:
            if s and s not in stock_set:
                stock_set.append(s)
    stocks_str = '、'.join(stock_set[:4]) if stock_set else '—'

    # WoW comparison from W19 data
    w19_c = w19['creators'].get(uid, {})
    w19_posts = w19_c.get('posts', [])
    w19_pc = len(w19_posts)
    w19_views = sum(p.get('views',0) for p in w19_posts)
    w19_likes = sum(p.get('likes',0) for p in w19_posts)
    wow_text = ''
    if w19_pc > 0:
        view_delta = c['browse'] - w19_views
        if w19_views > 0:
            view_pct = view_delta / w19_views * 100
            arrow = '↑' if view_pct >= 0 else '↓'
            wow_text = f'对比上周（W19 <b>{w19_pc}</b> 篇 / <b>{fmt_wan(w19_views)}</b> 浏览），本周浏览 <b>{arrow}{abs(view_pct):.0f}%</b>。'
    elif w19_pc == 0:
        wow_text = '上周（W19）未发布，本周恢复更新，<b>是积极信号</b>。'

    # Time pattern phrase
    time_pattern = ''
    if morning > pc * 0.5:
        time_pattern = '主要集中在<b>上午</b>'
    elif afternoon > pc * 0.5:
        time_pattern = '主要集中在<b>下午</b>'
    elif evening > pc * 0.5:
        time_pattern = '主要集中在<b>晚间</b>'
    elif night > pc * 0.5:
        time_pattern = '主要集中在<b>深夜</b>'
    else:
        time_pattern = f'分布跨度大（{period_str}）'

    # ─── Insight 1: 本周亮点 ───
    weekend_part = '<b>，含周末</b>' if has_weekend else ''
    insight1_b = (
        f'本周（5/11–5/17）共发布 <em>{pc}</em> 篇内容，<b>{day_count}/7 天活跃</b>{weekend_part}。'
        f'累计 <b>{fmt_wan(c["browse"])}</b> 浏览 · <b>{fmt_int(c["like"])}</b> 点赞 · <b>{fmt_int(c["comment"])}</b> 评论 · <b>{fmt_int(c["share"])}</b> 转发，'
        f'<b>篇均阅读 {fmt_int(avg_browse)}</b>，互动率 {eng_rate:.2f}%。'
    )
    if top_browse and top_browse.get('browse',0) > 0:
        insight1_b += (f'单篇阅读冠军：<a href="{feed_url(top_browse["fid"])}" target="_blank">'
                       f'《{esc(short_title(top_browse.get("title",""),24))}》</a> '
                       f'<em>{fmt_int(top_browse["browse"])}</em> 浏览 / <em>{top_browse["like"]}</em> 赞 / <em>{top_browse["comment"]}</em> 评论。')
    if wow_text:
        insight1_b += f' {wow_text}'

    # ─── Insight 2: 做得好的地方 ───
    strengths = []
    # Active days
    if day_count >= 5:
        strengths.append(f'<b>{day_count}/7 天高频在场</b>（包含{"周末" if has_weekend else "工作日全覆盖"}）：粉丝形成"每天都在"的稳定预期，是浏览基础的核心支撑。')
    elif day_count >= 3:
        strengths.append(f'<b>保持 {day_count} 天活跃节奏</b>：在普遍周中休息的同侪中，这个频率足以维持读者订阅心智。')
    # Top post performance
    if top_browse.get('browse',0) >= 500_000:
        strengths.append(f'<b>《{esc(short_title(top_browse.get("title",""),20))}》单篇 {fmt_wan(top_browse["browse"])}</b> 浏览，是当周圈内少数突破 50 万浏览的爆款，<b>说明您的标题钩子和议题切入精准</b>。')
    elif top_browse.get('browse',0) >= 100_000:
        strengths.append(f'最高单篇《{esc(short_title(top_browse.get("title",""),20))}》拿到 <b>{fmt_wan(top_browse["browse"])}</b> 浏览，足见您的选题和读者关注度高度匹配。')
    # Engagement quality
    if share_per_post >= 5 and pc <= 10:
        strengths.append(f'<b>转发量优秀</b>（篇均 {share_per_post:.1f} 转发）：内容"可分享性"强，读者愿意主动传播，这是含金量最高的信号。')
    if c['comment'] >= pc * 5 and pc > 0:
        strengths.append(f'<b>评论池活跃</b>（篇均 {c["comment"]/pc:.1f} 评论）：粉丝深度互动而非单纯阅读，社群粘性扎实。')
    # Time consistency
    if len(set(hours)) <= 4 and pc >= 3:
        strengths.append(f'<b>发布时段集中</b>（{period_str}），形成稳定阅读窗口预期，对算法权重和粉丝习惯都是加分项。')
    # Content type variety
    if len(types) >= 2 and pc >= 3:
        strengths.append(f'<b>内容形式有节奏感</b>：{esc(type_summary)}——单一形式容易疲劳，多元混合更能覆盖不同心智场景。')
    # Word count strength
    if avg_wc >= 1500:
        strengths.append(f'<b>篇均字数 {avg_wc}</b>，在快阅读时代坚持深度长文，自带研报感，建立了明确的"专业型作者"心智。')
    elif avg_wc <= 200 and pc >= 3:
        strengths.append(f'<b>篇均字数 {avg_wc}</b>：短小精悍的格式契合午盘 / 盘前的快决策需求，"5 分钟读完"是您的差异化优势。')
    # Stock coverage
    if len(stock_set) >= 4:
        strengths.append(f'<b>覆盖标的多元</b>（{esc(", ".join(stock_set[:4]))}），"一周一图谱"式的全市场视角是您与单股 KOL 的明确区隔。')
    if not strengths:
        strengths.append(f'本周持续更新 <b>{pc}</b> 篇，<b>累计 {fmt_wan(c["browse"])} 浏览</b>——在普遍流量回调的圈内环境下，能保持基本盘已属难得。')
    insight2_html = ''.join(f'<li>{s}</li>' for s in strengths[:4])

    # ─── Insight 3: 下周建议 ───
    suggestions = []
    # Suggestion 1: top post follow-up
    if top_browse.get('browse',0) >= 100_000:
        suggestions.append(f'<b>把《{esc(short_title(top_browse.get("title",""),18))}》做成系列</b>：单篇 {fmt_wan(top_browse["browse"])} 浏览证明这个角度极受欢迎，下周可补一篇兑现帖或续篇，<b>把一次性流量沉淀为长期 IP</b>。')
    # Suggestion 2: comment activation
    if pc > 0:
        cpr = c['comment'] / pc
        if cpr < 3 and avg_browse >= 50_000:
            suggestions.append(f'<b>评论池可激活</b>：篇均 {cpr:.1f} 评论，对 {fmt_int(avg_browse)} 篇均浏览来说偏低。建议在文末抛具体钩子（如"您手上 X 持仓比例多少？"），把"读完即走"转为留言区互动，平台二次推流权重会更高。')
    # Suggestion 3: weekday gap fill
    if not has_weekend and day_count <= 4:
        gap_days = [WEEKDAYS[i] for i in range(7) if i not in weekdays_set]
        if gap_days:
            suggestions.append(f'<b>补齐内容空窗</b>：本周{esc("/".join(gap_days[:3]))}未更新，建议在空窗日补一篇轻量"市场速评 / 周复盘"，强化"每周必看"的订阅心智。')
    # Suggestion 4: title pattern
    if pc >= 3:
        # Check title length variance
        title_lens = [len(p.get('title','')) for p in posts]
        if max(title_lens) - min(title_lens) > 25:
            suggestions.append(f'<b>标题长度差异大</b>：本周最短 {min(title_lens)} 字、最长 {max(title_lens)} 字混在一起，建议给短观点加固定前缀（如「⚡早盘速评」），让粉丝从标题就能预判阅读时长。')
    # Suggestion 5: share rate
    if pc > 0:
        spr = c['share'] / pc
        if spr < 1 and avg_browse >= 100_000:
            suggestions.append(f'<b>转发率仍可提升</b>：篇均 {spr:.1f} 转发，对篇均 {fmt_int(avg_browse)} 浏览偏低。建议在硬干货文末加一句"看到的朋友欢迎转发给关注 X 主线的同好"，或把核心观点做成可截图的金句卡片。')
    # Suggestion 6: WoW decline
    if w19_pc > 0 and pc < w19_pc * 0.5:
        suggestions.append(f'<b>本周产能回落明显</b>：W19 {w19_pc} 篇 → W20 {pc} 篇 / 跌 {round((w19_pc-pc)/w19_pc*100)}%，建议下周尽量稳回 W19 节奏，频率波动太大对算法推流不利。')
    # Suggestion 7: time pattern shift
    if night >= pc * 0.5 and pc >= 3:
        suggestions.append(f'<b>多数发布在深夜</b>，错过了早盘 / 午盘的黄金阅读窗口。建议挑 1–2 篇调整到 09:00–12:00 发布，可能带来更大初始浏览量。')
    # Suggestion 8: stock concentration
    if len(stock_set) <= 1 and pc >= 5:
        suggestions.append(f'<b>选题集中度过高</b>：本周仅围绕"{esc(stock_set[0]) if stock_set else "单一标的"}"展开，<b>读者新鲜感会下降</b>。建议穿插 1–2 个跨主线标的（如港股 / 黄金 / 加密），保持选题密度。')
    # Default fallback if list is short
    if len(suggestions) < 2:
        suggestions.append(f'<b>对齐市场主线</b>：本周热点为中美元首会面、美联储换届、半导体回调、港股IPO周。下周可挑一个您熟悉的角度切入，借势 + 信息增量是稳定流量的核心。')
    if len(suggestions) < 2:
        suggestions.append(f'<b>固定栏目化</b>：把您最具差异化的一篇（如本周阅读冠军）做成每周固定栏目，让粉丝形成"周X必看"的预期，是把单篇流量沉淀为长期资产的最快路径。')
    insight3_html = ''.join(f'<li>{s}</li>' for s in suggestions[:4])

    return f'''
      <div class="cs2-insight">
        <div class="cs2-insight-h">🌟 本周亮点</div>
        <div class="cs2-insight-b">{insight1_b}</div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">✅ 做得很好的地方（建议继续保持）</div>
        <div class="cs2-insight-b"><ul>{insight2_html}</ul></div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">💡 下周可以尝试的小优化</div>
        <div class="cs2-insight-b"><ul>{insight3_html}</ul></div>
      </div>'''


def gen_card_priority(uid, idx, m):
    """Priority card with cs2 block."""
    # Use priority_data if available (richer fields), else fall back to all data
    pd = priority_data['creators'].get(uid)
    c_full = w20['creators'].get(uid, {})
    posts = pd['posts'] if pd else c_full.get('posts',[])
    nick = (pd or c_full).get('nick') or m.get('nick') or f'用户{uid}'
    pc = (pd or c_full).get('post_count', len(posts))
    tb = (pd or c_full).get('browse', 0)
    tl = (pd or c_full).get('like', 0)
    tc = (pd or c_full).get('comment', 0)
    ts_ = (pd or c_full).get('share', 0)

    days = sorted({date_from_ts(p['ts']).strftime('%Y-%m-%d') for p in posts if p.get('ts')})
    day_count = len(days)
    fans = m.get('fans',0) or pd.get('fans') if pd else m.get('fans',0)
    accttype = m.get('accttype','personal')
    owner = m.get('owner','lisafu')
    cert = m.get('cert','')
    tier = 'tier-hi' if tb >= 1_000_000 else 'tier-mid' if tb >= 100_000 else 'tier-lo'
    eng = tl + tc*5 + ts_*10
    fans_inline = f'👥 {int(fans):,}' if fans else '👥 —'
    cert_html = f'<span class="cert-badge">{esc(cert)}</span>' if cert else ''
    search = esc(nick.lower())

    # Chips
    chips = []
    if pc == 0:
        chips.append('<span class="cs2-chip">📝 本周 <b>0</b> 篇发文</span>')
    else:
        types = Counter(FTYPE_MAP.get(p.get('ftype',0),'其他') for p in posts)
        type_summary = '、'.join(f'{t} {n}' for t,n in types.most_common(3))
        chips.append(f'<span class="cs2-chip">📝 发文 <b>{pc}</b> 篇（{esc(type_summary)}）</span>')
        chips.append(f'<span class="cs2-chip">📅 {day_count}/7 天活跃</span>')
        if posts:
            times = sorted([date_from_ts(p["ts"]).strftime("%H:%M") for p in posts])
            chips.append(f'<span class="cs2-chip">⏰ {times[0]}–{times[-1]}</span>')
        chips.append(f'<span class="cs2-chip">👁 总浏览 <b>{fmt_wan(tb)}</b></span>')

    # Peaks
    def peak_html(label, val, post, alt=False):
        cls = 'cs2-peak alt' if alt else 'cs2-peak'
        if not post or val == 0:
            return f'<div class="{cls}"><span class="cs2-peak-l">{label}</span> <span class="cs2-peak-v">—</span><span class="cs2-peak-t muted">本周无数据</span></div>'
        title_short = short_title(post.get('title','')) if post.get('title') else '（无标题）'
        return f'<div class="{cls}"><span class="cs2-peak-l">{label}</span> <span class="cs2-peak-v">{fmt_int(val)}</span><a class="cs2-peak-t" href="{feed_url(post["fid"])}" target="_blank">《{esc(title_short)}》</a></div>'

    if pc == 0:
        peaks_html = '<div class="cs2-peak"><span class="cs2-peak-l">本周</span> <span class="cs2-peak-v">未发文</span><span class="cs2-peak-t muted">建议查看上周内容并恢复更新</span></div>'
    else:
        def top(metric):
            return max(posts, key=lambda p: (p.get(metric,0), -p.get('ts',0)))
        p_b = top('browse'); p_l = top('like'); p_c = top('comment'); p_s = top('share')
        peaks_html = (
            peak_html('👁 浏览', p_b.get('browse',0), p_b) +
            peak_html('👍 点赞', p_l.get('like',0), p_l) +
            peak_html('💬 评论', p_c.get('comment',0), p_c, alt=True) +
            peak_html('🔁 转发', p_s.get('share',0), p_s, alt=True)
        )

    insights_html = gen_cs2_insights(uid, c_full, m)

    sorted_p = sorted(posts, key=lambda p:-p.get('ts',0))
    posts_html = ''.join(post_row_html(p) for p in sorted_p)
    stocks_row = stocks_row_html(posts)

    return f'''<div class="creator-card priority {tier}" data-uid="{uid}" data-posts="{pc}" data-views="{tb}" data-likes="{tl}" data-days="{day_count}" data-engagement="{eng}" data-fans="{fans or 0}" data-accttype="{accttype}" data-owner="{owner}" data-kol="yes" data-search="{search}">
  <div class="card-title">创作者周报 05.11–05.17</div>
  <div class="card-header">
    <div class="name-row">
      <a class="creator-name" href="https://q.futunn.com/profile/{uid}" target="_blank">{esc(nick)}</a>
      <span class="creator-uid">#{uid}</span>
      <span class="owner-tag">{owner}</span>
      <span class="fans-inline">{fans_inline}</span>
      {cert_html}
    </div>
    <div class="active-days-line">本周活跃 <b>{day_count}/7</b> 天</div>
  </div>
  <div class="card-data-section">
    <div class="card-data-label">本周内容</div>
    <div class="metrics-row">
      <div class="metric"><span class="num">{pc}</span><span class="lbl">原创内容</span></div>
    </div>
  </div>
  <div class="card-data-section">
    <div class="card-data-label">互动数据</div>
    <div class="metrics-row">
      <div class="metric"><span class="num">{fmt_int(tb)}</span><span class="lbl">浏览</span></div>
      <div class="metric"><span class="num">{fmt_int(tl)}</span><span class="lbl">获赞</span></div>
      <div class="metric"><span class="num">{fmt_int(tc)}</span><span class="lbl">评论</span></div>
      <div class="metric"><span class="num">{fmt_int(ts_)}</span><span class="lbl">被转发</span></div>
    </div>
  </div>
  <div class="cs2">
    <div class="cs2-chips">{''.join(chips)}</div>
    <div class="cs2-label">🏆 单篇峰值</div>
    <div class="cs2-peaks">{peaks_html}</div>
    <div class="cs2-pattern">
      <div class="cs2-pattern-title">📬 本周小结 · 给您的反馈</div>{insights_html}
    </div>
  </div>
  {stocks_row}
  <div class="card-disclaimer">上述內容由AI語言模型生成,僅供參考。以上內容不代表富途立場,不構成任何投資建議。</div>
  <details class="posts-detail">
    <summary>📋 查看全部帖子（{pc} 条）</summary>
    <div class="posts-list">{posts_html or '<div class="more-hint">本周无内容</div>'}</div>
  </details>
</div>'''


# ---------------- Build cards in priority-then-active-then... order ----------------
all_cards_html = []

# 1) Priority cards (in priority order)
for idx, uid in enumerate(PRIORITY_ORDER):
    m = meta.get(uid, {'fans':0,'accttype':'personal','owner':'lisafu','nick':'','cert':''})
    all_cards_html.append(gen_card_priority(uid, idx, m))

# 2) Other active creators (sort by browse desc)
other_active = [(uid,c) for uid,c in w20['creators'].items()
                if c['post_count']>0 and uid not in PRIORITY_SET]
other_active.sort(key=lambda x: -x[1]['browse'])
for uid,c in other_active:
    m = meta.get(uid, {'fans':0,'accttype':'personal','owner':'lisafu','nick':c.get('nick',''),'cert':''})
    all_cards_html.append(gen_card_simple(uid, c, m))

# 3) Inactive creators (NOT in priority — priority zero-post are still rendered as priority cards)
inactive_chips = []
inactive_count_real = 0
for uid in inactive_uids:
    if uid in PRIORITY_SET:
        continue  # already rendered as priority card
    inactive_count_real += 1
    m = meta.get(uid, {'fans':0,'accttype':'personal','owner':'lisafu','nick':w20['creators'][uid].get('nick','') or f'用户{uid}','cert':''})
    nick = w20['creators'][uid].get('nick') or m.get('nick') or f'用户{uid}'
    inactive_chips.append(
        f'<a class="inactive-chip" data-owner="{m["owner"]}" data-accttype="{m["accttype"]}" data-kol="no" '
        f'href="https://q.futunn.com/profile/{uid}" target="_blank">{esc(nick)}</a>'
    )

inactive_block = f'''<!-- 未活跃 -->
<div class="inactive-sec" id="inact" style="display:none">
  <h3 id="inact-h3">本周未发布内容（{inactive_count_real} 人）</h3>
  <div class="inactive-chips">{''.join(inactive_chips)}</div>
</div>
'''

# Update tab counts to reflect real active/inactive
# Active count includes priority + others (some priority have 0 posts and stay in active grid as cards)
# For tab labels we use:
active_in_grid = len(PRIORITY_ORDER) + len(other_active)  # all creator-cards
inactive_in_chips = inactive_count_real

# Replace the tab labels in ctrl_block (regenerate)
ctrl_block = ctrl_block.replace(f'活跃 ({active_count})', f'活跃 ({active_in_grid})')
ctrl_block = ctrl_block.replace(f'未发布 ({inactive_count})', f'未发布 ({inactive_in_chips})')
ctrl_block = ctrl_block.replace(f'显示 {active_count} 位', f'显示 {active_in_grid} 位')

# ---------------- JS ----------------
js_block = '''
<script>
let curTab='active', curType='all', curOwner='all', curKol='all';
const cards=()=>Array.from(document.querySelectorAll('.creator-card'));

function clearSearch(){
  document.getElementById('si').value='';
  document.getElementById('sc').style.display='none';
  filter();
}
function filter(){
  const q=document.getElementById('si').value.toLowerCase();
  document.getElementById('sc').style.display=q?'inline-block':'none';
  let n=0;
  cards().forEach(c=>{
    const srch=(c.dataset.search||'').toLowerCase();
    const id=(c.querySelector('.creator-uid')?.textContent||'').toLowerCase();
    const matchQ=!q||srch.includes(q)||id.includes(q);
    const matchT=curTab==='all'?true:curTab==='active'?+c.dataset.posts>0:+c.dataset.posts===0;
    const matchType=curType==='all'?true:c.dataset.accttype===curType;
    const matchOwner=curOwner==='all'?true:c.dataset.owner===curOwner;
    const matchKol=curKol==='all'?true:c.dataset.kol===curKol;
    c.classList.toggle('hidden',!(matchQ&&matchT&&matchType&&matchOwner&&matchKol));
    if(matchQ&&matchT&&matchType&&matchOwner&&matchKol) n++;
  });
  const showInact=curTab==='inactive'||curTab==='all';
  const inactSec=document.getElementById('inact');
  if(inactSec) inactSec.style.display=showInact?'':'none';
  let inactN=0;
  if(showInact){
    document.querySelectorAll('.inactive-chip').forEach(chip=>{
      const matchOwner=curOwner==='all'?true:chip.dataset.owner===curOwner;
      const matchType=curType==='all'?true:chip.dataset.accttype===curType;
      const matchKol=curKol==='all'?true:chip.dataset.kol===curKol;
      chip.style.display=(matchOwner&&matchType&&matchKol)?'':'none';
      if(matchOwner&&matchType&&matchKol) inactN++;
    });
    const h3=document.getElementById('inact-h3');
    if(h3) h3.textContent='本周未发布内容（'+inactN+' 人）';
  }
  document.getElementById('cl').textContent='显示 '+(n+inactN)+' 位';
}

function setTab(t,el){
  curTab=t;
  el.closest('.tabs').querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  filter();
}

function setType(t,el){
  curType=t;
  el.closest('.tabs').querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  filter();
}

function setOwner(o,el){
  // Owner buttons: only switch among owner tabs (skip KOL tabs which share same .tabs row)
  const ownerBtns=['blakeli','chuiszewu','kristrawzeng','lisafu','all'];
  el.closest('.tabs').querySelectorAll('.tab').forEach(x=>{
    const t=x.textContent.trim();
    if(t.startsWith('全部跟进人')||ownerBtns.some(o=>t===o)) x.classList.remove('on');
  });
  curOwner=o;
  el.classList.add('on');
  filter();
}

function setKol(k,el){
  el.closest('.tabs').querySelectorAll('.tab').forEach(x=>{
    const t=x.textContent.trim();
    if(t.startsWith('是否发送KOL周报')||t==='是'||t==='否') x.classList.remove('on');
  });
  curKol=k;
  el.classList.add('on');
  filter();
}

function resort(){
  const k=document.getElementById('ss').value;
  const g=document.getElementById('grid');
  const cs=[...g.querySelectorAll('.creator-card')];
  cs.sort((a,b)=>{
    const keys={posts:'posts',views:'views',likes:'likes',days:'days',fans:'fans'};
    return +b.dataset[keys[k]]-(+a.dataset[keys[k]]);
  });
  cs.forEach(c=>g.appendChild(c));
}
</script>
'''

# ---------------- Extract editor + opencc scripts from W19 (last two <script> blocks before </body>) ----------------
import re as _re
_w19_scripts = _re.findall(r'<script>\s*/\*\s*===\s*(?:KOL\s*反馈卡片编辑器|简繁切换).*?</script>', w19_html, _re.DOTALL)
editor_scripts = '\n'.join(s.replace("WEEK_TAG='W19'", "WEEK_TAG='W20'") for s in _w19_scripts)
print(f'  Editor/lang scripts extracted: {len(_w19_scripts)} blocks ({len(editor_scripts):,} chars)')

# Final HTML assembly
final_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>富途牛牛圈 创作者周报 2026-W20</title>
{css_block}
</head>
<body>
{header_block}
{kpi_block}
{owner_table}
{detail_row}
{top10_block}
{chart_block}
{ctrl_block}

<!-- 创作者卡片 -->
<div class="grid" id="grid">
{chr(10).join(all_cards_html)}
</div>

{inactive_block}

<div class="footer">富途牛牛圈 创作者运营周报 &nbsp;·&nbsp; 数据来源：q.futunn.com &nbsp;·&nbsp; 第20周 5/11–5/17 &nbsp;·&nbsp; 数据采集于 2026-05-18</div>
{js_block}
{editor_scripts}
</body>
</html>
'''

out_path = os.path.join(ROOT, 'index.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(final_html)
print(f'Wrote {out_path} ({len(final_html):,} bytes)')
print(f'  Priority cards: {len(PRIORITY_ORDER)}')
print(f'  Other active cards: {len(other_active)}')
print(f'  Inactive chips: {inactive_count_real}')
print(f'  Active total in grid: {active_in_grid}')
print(f'  Top10 likes: {len(top10_likes)}')
print(f'  Top10 stocks: {len(top_stocks)}')
print(f'  Top10 posters: {len(top_posters)}')
print(f'  Daily counts: {daily_counts}')
