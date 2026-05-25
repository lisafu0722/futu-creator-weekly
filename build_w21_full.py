"""
Build W21 index.html with full W20-style structure.
Var names kept: `w20` holds CURRENT (W21), `w19` holds PREVIOUS (W20).
"""
import json, os, html, re, hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
HK = timezone(timedelta(hours=8))

# ---------------- Load data ----------------
w20 = json.load(open(os.path.join(ROOT, 'w21_all_data.json'), encoding='utf-8'))
w19 = json.load(open(os.path.join(ROOT, 'w20_all177_data.json'), encoding='utf-8'))
priority_data = json.load(open(os.path.join(ROOT, 'w21_priority26_data.json'), encoding='utf-8'))
meta = json.load(open(os.path.join(ROOT, 'creator_meta.json'), encoding='utf-8'))

PRIORITY_ORDER = priority_data['priority_uids_order']
PRIORITY_SET = set(PRIORITY_ORDER)

# Backfill missing meta for new priority creators
# Manual owner assignment for priority KOLs not in W19 175-meta
NEW_PRIORITY_OWNERS = {
    '7109550': 'kristrawzeng', # 趋势就要HODL住
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
WEEK_DATES = ['2026-05-18','2026-05-19','2026-05-20','2026-05-21','2026-05-22','2026-05-23','2026-05-24']
WEEK_DATE_LABELS = ['5/18(一)','5/19(二)','5/20(三)','5/21(四)','5/22(五)','5/23(六)','5/24(日)']

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

# ---------------- CSS from W20 ----------------
w19_html = open(os.path.join(ROOT, 'weekly_report_2026W20_0511-0517.html'), encoding='utf-8').read()
css_block = w19_html[w19_html.index('<style>'):w19_html.index('</style>')+8]

# ---------------- Header ----------------
header_block = f'''<!-- 顶部标题 -->
<div class="hdr">
  <div class="hdr-badge">WEEK 21 · 2026</div>
  <h1>🐂 富途牛牛圈 创作者运营周报</h1>
  <div class="sub">2026 年第 21 周 &nbsp;·&nbsp; 5月18日（周一）— 5月24日（周日）</div>
  <div class="meta">数据采集于 2026-05-25 UTC+08:00 &nbsp;·&nbsp; 共纳入 {total_creators} 位创作者 &nbsp;·&nbsp; 26 位优先 KOL 含 cs2 反馈卡片</div>
  <div class="hdr-week-nav">
    <label>查看周报</label>
    <select onchange="if(this.value)location.href=this.value">
      <option value="index.html" selected>第21周（5/18–5/24）</option>
      <option value="weekly_report_2026W20_0511-0517.html">第20周（5/11–5/17）</option>
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
    <div class="ov-item ov-item-note"><span class="ov-icon">💡</span><span class="ov-item-note-text">本周市场围绕英伟达财报披露后的AI算力链估值、美联储议息会议表态与降息节奏、港股科网板块（腾讯/小米/阿里）的反复展开。港股新股周关注度仍高，成交回归优质内房与新消费；美股关注科技七巨头分化、半导体设备与黄金避险表现；加密市场比特币与稳定币立法持续发酵。</span></div>
    <div class="ov-topic-row">
      <div class="ov-topic-label">热议话题</div>
      <div class="ov-topic-tags"><span class="topic-tag">英伟达财报</span><span class="topic-tag">AI算力链</span><span class="topic-tag">美联储议息</span><span class="topic-tag">港股科网</span><span class="topic-tag">港股新股周</span><span class="topic-tag">黄金避险</span><span class="topic-tag">稳定币立法</span></div>
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


# ---------------- Hand-crafted overrides ----------------
# W20 hand-crafted narratives intentionally cleared for W21 — auto-gen now produces series-aware,
# diversified output. Add new overrides here only when a specific W21 narrative requires manual voice.
CUSTOM_INSIGHTS = {}
_W20_LEGACY_INSIGHTS = {
    # 孫子的末代傳人 — 4 篇 / 574万 / 双轨：长篇覆盘 + 比赛宣传 / 深夜更新 / 港股+美股
    '17296331': '''
      <div class="cs2-insight">
        <div class="cs2-insight-h">🌟 本周亮点：覆盘 IP 持续放大</div>
        <div class="cs2-insight-b">本周（5/11–5/17）以 <em>4</em> 篇产出拉出 <b>574 万</b> 累计浏览，<b>473 赞 · 137 评 · 44 转</b>——其中两篇深度覆盘（《模拟比赛正式开始：每日覆盘节奏》<em>292 万</em>、《持续不断创历史高位的美股与反复无常的港股》<em>156 万</em>）合计贡献 78% 流量，<b>"覆盘"这个个人栏目已经能稳定撬动百万级阅读</b>。同时配合两条 <b>"挑战月赚 20%"</b> 比赛宣发短贴铺信息密度，节奏组合拳打得很漂亮。对比上周（W19 5 篇 / 414 万浏览），本周浏览 <b>↑39%</b>，篇均阅读从 83 万拉到 <b>143 万</b>。</div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">✅ 做得很好的地方（建议继续保持）</div>
        <div class="cs2-insight-b"><ul>
          <li><b>"长篇深度 + 短贴宣发"双轨结构成型</b>：1700 字的复盘建立专业心智，13 字 / 84 字的比赛贴负责扩散触达，两类内容都各自跑出了好数据，是难得的内容矩阵雏形。</li>
          <li><b>港股 / 美股双战场并行</b>：本周覆盖了纳斯达克 100、恒指、阿里、英伟达、特斯拉、Meta 等跨市场标的，<b>"全市场视角"</b>是您与单股 / 单市场 KOL 的明确区隔，也是用户长期关注的关键理由。</li>
          <li><b>深夜（凌晨 1 点）发文形成识别度</b>：周一、周五凌晨 1 点准时上覆盘，<b>港股开盘前的"昨夜复盘 + 今晨预判"</b>正好踩中港美股交易者的查阅窗口，时间节奏已经被读者训练成习惯。</li>
          <li><b>《今个月将回到每日覆盘节奏》292 万浏览 / 196 赞</b>：单纯一句"恢复节奏"的承诺就能撬动这么大流量，说明读者对您的"日更复盘"有强期待，<b>这本身就是您最值钱的内容资产</b>。</li>
        </ul></div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">💡 下周可以尝试的小优化</div>
        <div class="cs2-insight-b"><ul>
          <li><b>把"每日覆盘"承诺兑现</b>：上周您公开承诺"今个月回到每日覆盘节奏"，但本周实际只有周一、周五两篇覆盘——读者带着期待来，落差会逐步消解信任。下周建议至少补到 <b>3 篇覆盘</b>，承诺与产出对齐，才能把这个 IP 的复利效应跑出来。</li>
          <li><b>比赛宣发贴整合而非重复</b>：5/12 17:39 与 5/14 20:54 两条「不同市况下，如何挑战比赛月赚 20%？」内容近乎重复（标题完全相同），第二条只拿到 47 万浏览（远低于第一篇 79 万）。<b>建议合并为一条带进度更新的"赛况日报"</b>，避免重复内容稀释互动。</li>
          <li><b>港股覆盘中给"恒指牛熊证"加交易回顾</b>：本周您覆盘里出现了「恒指瑞银八七牛 P.C」「恒指瑞银八二熊 Q.P」标的，但正文未细讲——这正是港股圈里"含金量最高、其他 KOL 最少触碰"的细分标的。下周可以单开一篇 <b>"牛熊证选用心得"</b>，差异化非常明显。</li>
          <li><b>评论钩子前置</b>：本周 137 条评论里 94 条集中在《不同市况挑战月赚 20%》这条短贴上（钩子是奖金 + 赛事），而长篇覆盘评论数仅个位数。建议在长文末尾加一句具体提问（如<b>"您现在港股仓位是几成？欢迎留言交流"</b>），把"读完即走"转为长尾互动。</li>
        </ul></div>
      </div>''',

    # 中戶變大戶小牛變大牛 — 2 篇 / 270万 / 超长篇技术解读 / ‼️㊙️ 标题 / 恒指+海力士专题
    '16751620': '''
      <div class="cs2-insight">
        <div class="cs2-insight-h">🌟 本周亮点：低频高质·两篇打天下</div>
        <div class="cs2-insight-b">本周（5/11–5/17）只出 <em>2</em> 篇内容，但单篇都是 <b>2500+ 字</b>的技术深读：周二《海力士为什么成为王者‼️中美谈判情况会如何㊙️》拿下 <em>200 万</em> 浏览（109 赞 / 22 评 / 14 转），周四《系统出现讯号‼️是机会还是散水㊙️》再拉 <em>70 万</em> 浏览。<b>两篇合计 270 万累计阅读 · 篇均阅读 135 万</b>——这是当周圈内"产能最低 / 单篇产值最高"的代表，<b>用 2 篇打出大部分人 5 篇都做不到的总流量</b>。对比上周（W19 1 篇 / 32 万浏览），本周浏览翻 <b>8.5 倍</b>，恢复节奏明显。</div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">✅ 做得很好的地方（建议继续保持）</div>
        <div class="cs2-insight-b"><ul>
          <li><b>‼️ + ㊙️ 的标题装饰已成 IP 标志</b>：在标题列表里一眼就能识别您的内容——这是个人辨识度最稀缺的东西。其他 KOL 模仿不来，<b>这是您最值钱的视觉锚点，建议固化为长期格式</b>。</li>
          <li><b>"重磅长篇 + 双钩子标题"路线打通</b>：标题前半"系统讯号 / 海力士成王"给硬干货预期，后半"是机会还是散水 / 谈判情况"给悬念，<b>读者刚看完标题就完成了"必须点开"的决定</b>。这种钩子结构是高浏览的核心引擎。</li>
          <li><b>专题切热点 + 系统讲方法</b>：海力士那篇借中美谈判 + 半导体热度切入（话题性 +1），系统讯号那篇沉淀方法论（专业性 +1）——<b>这种"热点叙事 / 方法巩固"的交替节奏</b>是您能稳定输出的根基。</li>
          <li><b>专注恒指 + 海力士窄而深</b>：标的就是恒指期货、南方两倍做多海力士这一个体系，<b>窄反而是您的优势</b>——大量分散的 KOL 看上去什么都讲，但您的"恒指系统派"读者标签鲜明，粘性更高。</li>
        </ul></div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">💡 下周可以尝试的小优化</div>
        <div class="cs2-insight-b"><ul>
          <li><b>周中（周三）补一条短帖维持节奏</b>：本周只在周二、周四出文，<b>周三 / 周五 / 周末完全空窗</b>。哪怕只是 200 字"系统讯号截图速览"，也能让粉丝知道账号在线，避免"两天不见就以为停更"的订阅流失。</li>
          <li><b>把《系统讯号》做成连载序号</b>：本周《系统出现讯号‼️是机会还是散水㊙️》是经典框架，下周可加 <b>"#系统讯号 02"</b> 序号开始连载——读者一旦认识连载，<b>每周二 / 四会主动来翻新一期</b>，把"单篇爆款"沉淀为"栏目订阅"。</li>
          <li><b>海力士这条 200 万浏览要承接</b>：单篇拿到 200 万浏览说明读者对"海力士专题"有强需求，但仅 22 条评论 + 14 条转发，<b>对这个浏览量来说转化偏低</b>。下周建议出篇 <b>"海力士读者问答合集"</b>，把上一篇评论区的核心问题展开回答，既复用流量、又拉升评论池厚度。</li>
          <li><b>2500+ 字超长篇可拆段强化</b>：周二那篇 2486 字、周四 2970 字一气呵成读完成本高。建议在长文里加 <b>3–4 个清晰小标题</b>（如「一、海力士基本面」「二、与中美谈判联动」），既提升可读性，也让读者方便截屏分享某一段——分享率会跟着提升。</li>
        </ul></div>
      </div>''',

    # 年頭旺到年尾（师姐）— 3 篇 / 134万 / 「X月X日覆盘」已系列化 / 多在清晨 5 点发布
    '23462267': '''
      <div class="cs2-insight">
        <div class="cs2-insight-h">🌟 本周亮点：覆盘连载稳定输出</div>
        <div class="cs2-insight-b">本周（5/11–5/17）以 <em>3</em> 篇<b>「X月X日覆盘」连载</b>拉出 <b>134 万</b>累计浏览、<b>487 赞 · 84 评 · 10 转</b>，<b>篇均阅读 44.8 万</b>。其中 5/13《5月12日覆盘》清晨 05:23 发布，单篇冠军 <em>73 万</em> 浏览（184 赞 / 25 评）；5/14《5月13日覆盘》05:22 上线 <em>47 万</em> 浏览（188 赞 / 32 评）；周日 23:50《5月15日覆盘》<em>14 万</em>。<b>「师姐覆盘」这个固定栏目已经成型</b>——不需要解释「这篇讲什么」，标题里的日期就是订阅信号。</div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">✅ 做得很好的地方（建议继续保持）</div>
        <div class="cs2-insight-b"><ul>
          <li><b>「X月X日覆盘」连载格式已沉淀为个人 IP</b>：3 篇标题统一格式（5月12日覆盘 / 5月13日覆盘 / 5月15日覆盘），<b>读者一眼就知道是您的「日历式」覆盘</b>——这种命名规范化是绝大多数 KOL 做不到的，建议固化下去。</li>
          <li><b>清晨 05:22 / 05:23 准时上线，是非常稀缺的发布时段</b>：港股 09:30 开盘前 4 小时、刚好覆盖欧美收盘 + 港股早盘前查阅窗口——<b>「师姐每天 5 点的覆盘」</b>已经训练成读者的晨间习惯，请保持。</li>
          <li><b>互动质量是强项</b>：篇均 162 赞 / 28 评论，在覆盘类内容里属于明显高互动——说明读者不只是浏览，是真的在读、在留言交流，<b>社群粘性比单纯爆款 KOL 更扎实</b>。</li>
          <li><b>标的体系覆盖港 / 美 / A 三市场联动</b>：恒指 + 恒指期货 + 纳指综合 + 上证指数 + 腾讯——<b>「跨市场视角」</b>是您与单市场覆盘 KOL 的核心区隔，对港股交易者尤其有用。</li>
        </ul></div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">💡 下周可以尝试的小优化</div>
        <div class="cs2-insight-b"><ul>
          <li><b>周日 23:50 那篇偏离您的招牌时段</b>：清晨 5 点是您训练读者的<b>固定窗口</b>，但《5月15日覆盘》在周日深夜才发——读者周一清晨打开时已经"过夜"，错过早盘黄金阅读期，单篇浏览也明显低于另外两篇（14 万 vs 73 万 / 47 万）。<b>下周建议把覆盘统一锁死在 5–6 点这个时段</b>，深夜发布会稀释您「师姐 5 点准时」的招牌识别度。</li>
          <li><b>「日历」可补齐到每个交易日</b>：本周覆盘了 5/12、5/13、5/15，但 5/14 周四（市场有反应）、5/16 周五（一周收官）的覆盘缺失——<b>对「日历式连载」来说，缺一天就破了"每天都有"的承诺</b>。下周建议尽量做到工作日 5 篇全覆盖，这是您的连载相对其他 KOL 的最大壁垒。</li>
          <li><b>转发率仍可拉一拉</b>：本周累计 10 转 / 134 万浏览（篇均 3.3 转），对篇均 44 万浏览来说偏低。建议每篇文末加一句具体钩子，比如<b>"今日观点欢迎截图分享给做恒指的朋友"</b>，把强阅读转化为强传播。</li>
          <li><b>纯文字覆盘可加 1 张固定视觉锚点</b>：本周 3 篇都是纯文字（394 / 675 / 965 字），建议每篇固定附 1 张<b>恒指日 K 截图 + 关键位标注</b>，让读者"3 秒看走势"——对手机端阅读体验和分享率都会有显著加成，也强化"师姐覆盘 = 看图就懂"的视觉识别。</li>
        </ul></div>
      </div>''',

    # 股海GSO — 2 篇 / 199万 / 日记体连载 / DDMMYYYY 格式标题 / 恒指+港股蓝筹
    '25169348': '''
      <div class="cs2-insight">
        <div class="cs2-insight-h">🌟 本周亮点：日更日记·节奏稳定</div>
        <div class="cs2-insight-b">本周（5/11–5/17）出 <em>2</em> 篇内容，<b>都是日记式标题</b>——《13052026 (三) 访华期间上下波动》拉到 <em>121 万</em> 浏览（108 赞 / 21 评 / 9 转），《14052026 (四) 静待 ☕️》紧接 <em>78 万</em> 浏览。<b>两天连续日更</b>，累计 <b>199 万浏览 · 204 赞 · 36 评 · 21 转</b>，篇均字数 940 字（不长不短刚好"早盘前 5 分钟读完"的篇幅）。对比上周（W19 5 篇 / 246 万浏览），本周虽然篇数减半，<b>但篇均阅读从 49 万拉到 99 万</b>，单篇质量拉升明显。</div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">✅ 做得很好的地方（建议继续保持）</div>
        <div class="cs2-insight-b"><ul>
          <li><b>「DDMMYYYY (周X) 主题」日记格式独一份</b>：在恒指 KOL 群里标题就能一眼区分，<b>「14052026 (四) 静待 ☕️」</b>这种格式既给日期锚点又留情绪——读者一看就知道是"GSO 的港股日记"。这种格式辨识度比单纯的标题党更长效。</li>
          <li><b>☕️ 这个个人符号用得很妙</b>：恒指 / 海力士其他 KOL 都没有用，<b>☕️ 暗示"今天就坐着看，不冲"的克制态度</b>，是个人观点的视觉化——这种小符号每周固定出现 1–2 次，比反复说"理性观望"更有 IP 感。</li>
          <li><b>恒指 + 港股蓝筹组合稳健</b>：本周覆盖了恒指期货、阿里巴巴 -W、腾讯控股、南方 A50——<b>这套"恒指 + 蓝筹"组合就是您的固定标的池</b>，对新读者来说"看您一篇就掌握港股核心标的"，留存率会比标的乱跳的 KOL 高。</li>
          <li><b>盘前 / 盘后两个时点都能切入</b>：周三 22:02（港股盘后）、周四 21:14（港股盘后）——<b>港股盘后这个时段读者最闲、查阅意愿最强</b>，您的发布节奏正好踩在这条曲线上，是周三那篇能拿 121 万的隐性原因。</li>
        </ul></div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">💡 下周可以尝试的小优化</div>
        <div class="cs2-insight-b"><ul>
          <li><b>周一 / 周五补充周报式日记</b>：本周仅周三 / 周四两篇，<b>周一（开盘日）和周五（收盘日）这两个最容易拉流量的节点完全没占位</b>。下周可加《<b>周一开盘前观察</b>》《<b>周五本周总结</b>》两条标准化日记，把"GSO 日记"覆盖到"全周关键节点"。</li>
          <li><b>评论钩子可以更主动</b>：本周 36 条评论 / 199 万浏览（评论率 0.018%）——以您的浏览基数应该能拉更多。建议每篇日记最后加一句 <b>"您今天港股是加仓还是减仓？☕️or 🔥"</b> 这种二选一的轻互动钩子，把读者拉进留言区。</li>
          <li><b>日记给加一个固定副标题区分主题</b>：标题《访华期间上下波动》《静待 ☕️》信息密度可以更高。建议在日期后面加上 <b>1 个核心事件标签</b>（如「13052026 (三) | #中美谈判」），<b>既保持日记格式又能让读者通过 # 标签翻历史</b>，是日记 IP 长尾化的关键一步。</li>
          <li><b>日记体扩展周末特辑</b>：日记系列目前只在交易日出现，但周末市场静默正是输出"周末特辑：本周三大趋势复盘"的好时机。<b>周末出一篇 1500 字深度版日记</b>，能让"GSO 日记"从"工作日陪伴"扩展到"全周陪伴"，订阅心智更稳。</li>
        </ul></div>
      </div>''',
}

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

def uid_pick(uid, salt, options):
    """Deterministic pick from options based on uid+salt — same KOL always gets same wording, different KOLs get different ones."""
    h = int(hashlib.md5(f'{uid}-{salt}'.encode()).hexdigest(), 16)
    return options[h % len(options)]


def detect_series(posts):
    """Detect serialized title pattern. Returns label (str) or None."""
    titles = [p.get('title','') for p in posts if p.get('title')]
    if len(titles) < 2:
        return None
    daily_pat = re.compile(r'^\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日')
    if sum(1 for t in titles if daily_pat.match(t)) >= 2:
        return '「X月X日…」每日复盘体'
    if sum(1 for t in titles if re.match(r'^\d{6,8}', t)) >= 2:
        return '日期前缀日记体'
    bracket_pat = re.compile(r'^[【\[]([^】\]]{1,8})[】\]]')
    bracket_groups = Counter()
    for t in titles:
        m = bracket_pat.match(t)
        if m:
            bracket_groups[m.group(1)] += 1
    for tag, cnt in bracket_groups.items():
        if cnt >= 2:
            return f'「【{tag}】」固定栏目'
    if len(titles) >= 3:
        prefix_groups = Counter(t[:4] for t in titles if len(t) >= 4)
        threshold = max(2, len(titles)//2)
        for prefix, cnt in prefix_groups.items():
            if cnt >= threshold and not prefix.isspace():
                return f'「{prefix}…」固定开头'
    return None


def gen_cs2_insights(uid, c, m):
    """Generate richer cs2 reflection blocks."""
    # Hand-crafted overrides for KOLs in same WeChat group (avoid feeling templated)
    if uid in CUSTOM_INSIGHTS:
        return CUSTOM_INSIGHTS[uid]
    posts = c.get('posts',[])
    pc = c['post_count']
    nick = c.get('nick') or m.get('nick') or f'用户{uid}'

    # Zero-post case
    if pc == 0:
        # Check W19 stats for comparison
        w19_c = w19['creators'].get(uid, {})
        w19_pc = len(w19_c.get('posts', []))
        w19_views = sum(p.get('browse',0) for p in w19_c.get('posts',[]))
        had_w19 = w19_pc > 0
        if had_w19:
            hint = (f'对比上周（W20）您发布了 <em>{w19_pc}</em> 篇文章 / <em>{fmt_wan(w19_views)}</em> 浏览，'
                    f'本周完全断更，<b>读者订阅曲线和平台权重都会受影响</b>。建议尽快了解断更原因（休假 / 选题枯竭 / 时间冲突？）')
        else:
            hint = '上周也未发布，<b>账号已连续两周静默</b>，建议主动沟通是否仍有继续创作的意愿。'

        topics = '英伟达财报与AI算力链 / 美联储议息会议 / 港股科网走势 / 比特币震荡 / 黄金避险 / 港股新股周'
        return f'''
      <div class="cs2-insight">
        <div class="cs2-insight-h">📭 本周状态</div>
        <div class="cs2-insight-b">本周（5/18–5/24）<b>暂无原创内容发布</b>。{hint}</div>
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

    # WoW comparison from W20 data (previous week)
    w19_c = w19['creators'].get(uid, {})
    w19_posts = w19_c.get('posts', [])
    w19_pc = len(w19_posts)
    w19_views = sum(p.get('browse',0) for p in w19_posts)
    w19_likes = sum(p.get('like',0) for p in w19_posts)
    wow_text = ''
    if w19_pc > 0:
        view_delta = c['browse'] - w19_views
        if w19_views > 0:
            view_pct = view_delta / w19_views * 100
            arrow = '↑' if view_pct >= 0 else '↓'
            wow_text = f'对比上周（W20 <b>{w19_pc}</b> 篇 / <b>{fmt_wan(w19_views)}</b> 浏览），本周浏览 <b>{arrow}{abs(view_pct):.0f}%</b>。'
    elif w19_pc == 0:
        wow_text = '上周（W20）未发布，本周恢复更新，<b>是积极信号</b>。'

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
        f'本周（5/18–5/24）共发布 <em>{pc}</em> 篇内容，<b>{day_count}/7 天活跃</b>{weekend_part}。'
        f'累计 <b>{fmt_wan(c["browse"])}</b> 浏览 · <b>{fmt_int(c["like"])}</b> 点赞 · <b>{fmt_int(c["comment"])}</b> 评论 · <b>{fmt_int(c["share"])}</b> 转发，'
        f'<b>篇均阅读 {fmt_int(avg_browse)}</b>，互动率 {eng_rate:.2f}%。'
    )
    if top_browse and top_browse.get('browse',0) > 0:
        insight1_b += (f'单篇阅读冠军：<a href="{feed_url(top_browse["fid"])}" target="_blank">'
                       f'《{esc(short_title(top_browse.get("title",""),24))}》</a> '
                       f'<em>{fmt_int(top_browse["browse"])}</em> 浏览 / <em>{top_browse["like"]}</em> 赞 / <em>{top_browse["comment"]}</em> 评论。')
    if wow_text:
        insight1_b += f' {wow_text}'

    # Series detection — used by both strengths and suggestions
    series_label = detect_series(posts)

    # Title sentiment markers / length stats
    title_lens = [len(p.get('title','')) for p in posts] or [0]
    title_len_spread = max(title_lens) - min(title_lens)
    emo_count = sum(1 for p in posts if re.search(r'[?!？！]{2,}|[‼❗❓⁉]', p.get('title','')))
    no_stock_ratio = sum(1 for p in posts if not p.get('stocks')) / max(pc,1)

    # Single-post dominance
    top_browse_share = (top_browse.get('browse',0) / max(c['browse'],1)) if c['browse'] else 0

    # Type concentration
    main_type, main_type_n = types.most_common(1)[0] if types else ('其他',0)
    type_concentration = main_type_n / max(pc,1)

    # WoW positive
    wow_pos = (w19_pc > 0 and w19_views > 0 and c['browse'] >= w19_views * 1.5)

    # Engagement subtleties
    cpr = c['comment'] / max(pc,1)
    spr = c['share'] / max(pc,1)
    lpr = c['like'] / max(pc,1)
    high_like_low_share = (lpr >= 30 and spr < 1 and pc >= 2)

    # ─── Insight 2: 做得好的地方（≤3 条） ───
    strengths = []
    # 系列已成型 — 优先级最高，因为这是创作者真实功夫
    if series_label:
        strengths.append(uid_pick(uid, 'series_strength', [
            f'<b>{esc(series_label)}已稳定输出</b>：连续输出形成的"栏目记忆"是单篇爆款换不来的资产，订阅曲线最稳的就是这种格式。',
            f'<b>{esc(series_label)}成形度高</b>：粉丝点进您主页一眼就能识别"这是 XX 的招牌"，比任何运营推位都管用。',
            f'<b>已建立{esc(series_label)}的栏目识别度</b>：连载本身就是护城河——每一篇都在为下一篇导流，复利效应明显。',
        ]))
    # WoW 正向信号
    if wow_pos:
        strengths.append(uid_pick(uid, 'wow_pos', [
            f'<b>本周浏览较 W20 增长 {round((c["browse"]-w19_views)/w19_views*100)}%</b>：在圈内整体回调的环境里跑出反向曲线，说明选题踩中了主线。',
            f'<b>WoW 浏览翻倍级（{fmt_wan(w19_views)}→{fmt_wan(c["browse"])}）</b>：增长不是偶然，是您本周的角度被算法和读者同时认可。',
        ]))
    # Active days
    if day_count >= 5:
        strengths.append(uid_pick(uid, 'high_freq', [
            f'<b>{day_count}/7 天高频在场</b>{"（含周末）" if has_weekend else "（工作日全勤）"}：粉丝形成"每天都在"的预期，这是浏览基础最稳的来源。',
            f'<b>本周 {day_count} 天活跃</b>{"，周末也在" if has_weekend else "覆盖整个工作日"}：高频在场带来的算法权重提升不容易被波动打散。',
        ]))
    elif day_count >= 3 and pc >= 3:
        strengths.append(uid_pick(uid, 'mid_freq', [
            f'<b>{day_count} 天稳定节奏</b>：在普遍周中断更的同侪中，这个频率已经足以维持读者订阅心智。',
            f'<b>{day_count} 天分布</b>：不堆产、不躺平，节奏感对长期订阅者最友好。',
        ]))
    # Top post
    tb_views = top_browse.get('browse',0)
    if tb_views >= 500_000:
        strengths.append(f'<b>《{esc(short_title(top_browse.get("title",""),20))}》单篇 {fmt_wan(tb_views)}</b> 浏览，是当周圈内少数破 50 万的爆款，<b>标题钩子和议题切入精准</b>。')
    elif tb_views >= 100_000:
        strengths.append(uid_pick(uid, 'top10w', [
            f'最高单篇《{esc(short_title(top_browse.get("title",""),20))}》拿到 <b>{fmt_wan(tb_views)}</b> 浏览，选题与读者关注度高度匹配。',
            f'《{esc(short_title(top_browse.get("title",""),20))}》冲到 <b>{fmt_wan(tb_views)}</b>：这种破 10 万级单篇是账号势能的最直接体现。',
        ]))
    # 转发优秀
    if spr >= 5 and pc <= 10:
        strengths.append(f'<b>转发量优秀</b>（篇均 {spr:.1f}）：内容"可分享性"强，读者愿意主动传播，这是含金量最高的信号。')
    # 评论池活跃
    if cpr >= 5 and pc > 0:
        strengths.append(uid_pick(uid, 'comment_hot', [
            f'<b>评论池活跃</b>（篇均 {cpr:.1f} 评论）：粉丝在留言区深度互动，社群粘性扎实。',
            f'<b>篇均 {cpr:.1f} 条评论</b>：留言区已经形成"读者会主动来聊"的氛围，是 KOL → 社群的关键一跃。',
        ]))
    # 时段集中
    if len(set(hours)) <= 4 and pc >= 3 and not series_label:
        strengths.append(f'<b>发布时段集中</b>（{period_str}）：形成稳定阅读窗口预期，对算法权重和粉丝习惯都是加分项。')
    # 内容多元
    if len(types) >= 3 and pc >= 4:
        strengths.append(f'<b>内容形式多线推进</b>（{esc(type_summary)}）：单一形式容易疲劳，多元组合更能覆盖不同阅读心智。')
    # 字数差异化
    if avg_wc >= 1500:
        strengths.append(uid_pick(uid, 'long', [
            f'<b>篇均 {avg_wc} 字</b>：在快阅读时代坚持深度长文，自带研报感，"专业型作者"心智已立。',
            f'<b>{avg_wc} 字篇均</b>：长文密度让账号天然带着研报权重，读者对单篇的信任阈值会更低。',
        ]))
    elif avg_wc <= 200 and pc >= 4:
        strengths.append(f'<b>篇均 {avg_wc} 字</b>：短小精悍契合午盘/盘前的快决策场景，"5 分钟读完"是您的差异化点。')
    # 标的覆盖
    if len(stock_set) >= 4:
        strengths.append(f'<b>覆盖标的多元</b>（{esc("、".join(stock_set[:4]))}）：全市场视角是您与单股 KOL 的明确区隔。')
    # 单股深耕（与上一条互斥）
    if len(stock_set) == 1 and pc >= 4:
        strengths.append(f'<b>专注「{esc(stock_set[0])}」深耕</b>：在 KOL 普遍泛主题的环境里，单股深度是稀缺定位，搜索流量也更容易聚拢。')
    # 互动率高
    if eng_rate >= 1.5 and pc >= 2:
        strengths.append(f'<b>互动率 {eng_rate:.2f}%</b>：高于圈内大多数 KOL，说明读者不是路过、是真在意您说什么。')
    # Fallback
    if not strengths:
        strengths.append(f'本周持续更新 <b>{pc}</b> 篇 / <b>{fmt_wan(c["browse"])}</b> 浏览：在普遍回调的圈内环境下保持基本盘已属难得。')
    insight2_html = ''.join(f'<li>{s}</li>' for s in strengths[:3])

    # ─── Insight 3: 下周可以尝试的小优化（≤3 条） ───
    suggestions = []
    # 系列已成型 → 升级而非"做成系列"
    if series_label:
        suggestions.append(uid_pick(uid, 'series_upgrade', [
            f'<b>{esc(series_label)}的"目录化"</b>：在主页置顶或在最新一篇文末，加一段"系列索引"链回过往 3–5 篇，让新读者一进来就能"补课式订阅"。',
            f'<b>给{esc(series_label)}做一次月度合集</b>：把过去 4 周里点击最高的 3 篇整合成"月度精华回看"，是把单篇流量沉淀为长期资产的快路径。',
            f'<b>{esc(series_label)}加一条"导读线"</b>：在每篇开头用 1 行讲清"上一篇我们看到 X，今天看 Y"，连续阅读体验比单篇质量更能留住订阅。',
        ]))
    elif tb_views >= 100_000:
        suggestions.append(uid_pick(uid, 'make_series', [
            f'<b>把《{esc(short_title(top_browse.get("title",""),18))}》延展为短系列</b>：单篇 {fmt_wan(tb_views)} 浏览证明角度受欢迎，下周补一篇兑现帖或续篇，把一次性流量沉淀。',
            f'<b>《{esc(short_title(top_browse.get("title",""),18))}》后续可做"复盘×预判"双稿</b>：先复盘单篇为何爆，再对同一议题给下周判断，单篇变两点曝光。',
        ]))

    # 头部一篇打天下（风险信号）
    if top_browse_share > 0.6 and pc >= 3:
        suggestions.append(uid_pick(uid, 'head_concentrated', [
            f'<b>头部依赖度偏高</b>：《{esc(short_title(top_browse.get("title",""),16))}》一篇占了本周 {top_browse_share*100:.0f}% 浏览，其余文章未跑出来。建议复盘头部为何赢、把同方法论复用到 1–2 篇腰部内容。',
            f'<b>本周浏览的 {top_browse_share*100:.0f}% 集中在 1 篇</b>：腰部文章拉力不足，下周可针对腰部文章重做标题/首段，看能否把分布拉平。',
        ]))

    # 内容形式偏科
    if type_concentration >= 0.85 and pc >= 4 and not series_label:
        suggestions.append(f'<b>形式过于单一</b>：本周 {pc} 篇里 {main_type_n} 篇是"{main_type}"，{type_concentration*100:.0f}% 同质。建议穿插 1 篇视频/投票/短评换节奏，避免读者审美疲劳。')

    # 评论池可激活
    if cpr < 3 and avg_browse >= 50_000:
        suggestions.append(uid_pick(uid, 'comment_low', [
            f'<b>评论池可激活</b>：篇均 {cpr:.1f} 评论 vs {fmt_int(avg_browse)} 篇均浏览，比例偏低。可在文末抛具体钩子（如"您仓位 X 占比多少？"），引导留言。',
            f'<b>{cpr:.1f} 评论/篇 在 {fmt_int(avg_browse)} 浏览面前偏冷</b>：建议挑 1 篇试试"问题式收尾"——结尾留一个非二选一的开放问题，往往能把潜水读者拉出来。',
        ]))

    # 选题集中（>=5篇仅围绕≤1标的）— 只在没系列、没专注定位时提
    if len(stock_set) <= 1 and pc >= 5 and not series_label:
        focus = esc(stock_set[0]) if stock_set else '单一标的'
        suggestions.append(f'<b>选题密度可调</b>：本周 {pc} 篇集中在「{focus}」，建议穿插 1–2 个跨主线（港股新股/黄金/加密）保持新鲜感。')

    # 选题过散（≥6 标的且 pc≤6 → 没有故事线）
    if len(stock_set) >= 6 and pc <= 6:
        suggestions.append(f'<b>本周选题略散</b>：{pc} 篇覆盖了 {len(stock_set)} 个标的，没有形成明显主线。下周可挑 1 个最高确信的方向连写 2 篇，给读者一个"跟着您走"的入口。')

    # 标题情绪化
    if emo_count >= max(2, pc//2) and pc >= 3:
        suggestions.append(f'<b>标题情绪化标点偏多</b>（{emo_count}/{pc} 篇含 ?? !! 类）：圈内"惊叹号疲劳"已经出现，下周试试用具体数字代替强调号（"三月以来 7 次反弹"比"惊天反弹‼️" 更让人想点）。')

    # 缺股票标签
    if no_stock_ratio >= 0.4 and pc >= 4:
        suggestions.append(f'<b>{int(no_stock_ratio*100)}% 文章未关联标的</b>：股票圈的搜索流量很依赖标的标签，建议每篇至少绑 1 个相关标的，搜索曝光会显著提升。')

    # 周末空窗
    if not has_weekend and day_count <= 4:
        gap_days = [WEEKDAYS[i] for i in range(5) if i not in weekdays_set]  # 工作日 gap 优先
        if gap_days:
            suggestions.append(uid_pick(uid, 'gap_fill', [
                f'<b>{esc("、".join(gap_days[:2]))}空窗</b>：建议在空窗日补一篇轻量"盘前速评/周复盘"，强化"每周必看"的订阅心智。',
                f'<b>本周 {esc(gap_days[0])} 没更新</b>：工作日空窗会让上一篇的浏览曲线提前断尾，节奏上"每天有声"的成本其实只是 200–500 字。',
            ]))

    # 标题长度差异
    if title_len_spread > 25 and pc >= 4 and not series_label:
        suggestions.append(f'<b>标题长度跨度大</b>：本周最短 {min(title_lens)} 字、最长 {max(title_lens)} 字。给短观点加固定前缀（如「⚡早盘速评」），让粉丝从标题就能预判阅读时长。')

    # 转发率
    if spr < 1 and avg_browse >= 100_000:
        suggestions.append(uid_pick(uid, 'share_low', [
            f'<b>转发率仍有空间</b>：篇均 {spr:.1f} 转发 vs {fmt_int(avg_browse)} 浏览偏低。建议在硬干货文末加一句"看到的朋友欢迎转给关注 X 主线的同好"，或把核心观点做成可截图金句卡。',
            f'<b>{spr:.1f} 转发/篇 vs {fmt_int(avg_browse)} 浏览</b>：内容质量没问题，但缺一个"让人想转"的钩子。试试金句加粗 + 文末 1 句"转给会用得上的人"。',
        ]))

    # WoW 回落
    if w19_pc > 0 and pc < w19_pc * 0.5:
        suggestions.append(f'<b>本周产能回落明显</b>：W20 {w19_pc} 篇 → W21 {pc} 篇 / 跌 {round((w19_pc-pc)/w19_pc*100)}%，建议下周回到 W20 节奏，频率波动太大对推流权重不利。')

    # WoW 翻倍 → 加投
    if wow_pos and pc >= 2:
        suggestions.append(f'<b>本周已跑出增长</b>，建议趁热加 1 篇与"{esc(short_title(top_browse.get("title",""),12))}"同主题的延伸稿，把上升势头多续 1 周。')

    # 凌晨/深夜发文
    if night >= pc * 0.5 and pc >= 3:
        suggestions.append(uid_pick(uid, 'night', [
            f'<b>多数发布在深夜（{night}/{pc} 篇 0–6 点）</b>，错过了早盘/午盘黄金阅读窗口。建议挑 1–2 篇调到 09:00–12:00 发布。',
            f'<b>本周 {night}/{pc} 篇在 0–6 点发出</b>：港美股圈这个时段读者基数小，调到早盘前后浏览能直接 ×2。',
        ]))

    # 长文无锚点
    if avg_wc >= 1500 and lpr < 20 and pc >= 2:
        suggestions.append(f'<b>长文需要"读得下去"的视觉锚点</b>：篇均 {avg_wc} 字但篇均 {lpr:.0f} 赞偏低，建议加 H3 小标题/数字编号/加粗金句，让快速翻阅者也能抓到重点。')

    # 短评太短
    if avg_wc < 300 and pc >= 4 and tb_views < 100_000:
        suggestions.append(f'<b>短评偏多但浏览未起</b>：{avg_wc} 字篇均 + 单篇最高 {fmt_wan(tb_views)} 浏览，建议每周挑 1 篇做到 800–1200 字"中等深度"，给账号注入"重头戏"权重。')

    # 高赞低转
    if high_like_low_share:
        suggestions.append(f'<b>高赞低转</b>（篇均 {lpr:.0f} 赞 / {spr:.1f} 转发）：读者认同您但没动力分享，可在文末加一句"如果对 X 主线感兴趣，欢迎转给同好"，把认同转为传播。')

    # Fallback (only if list still short)
    if len(suggestions) < 2:
        suggestions.append(uid_pick(uid, 'fallback_macro', [
            f'<b>对齐市场主线</b>：本周热点（英伟达财报与AI算力链、美联储议息、港股科网走势、稳定币与加密叙事）下周仍会发酵，可挑 1 个您熟悉的角度切入。',
            f'<b>下周可借势</b>：宏观叙事仍在演化（AI算力/联储/港股科网/黄金避险），从您熟悉的标的角度切一篇"我对 X 的判断没变"，是借势 + 信息增量的组合拳。',
        ]))
    if len(suggestions) < 2:
        suggestions.append(f'<b>下周建议</b>：固定一个"周X必出"的栏目锚点（如"周一盘前/周日复盘"），让粉丝从节奏开始记住您。')
    insight3_html = ''.join(f'<li>{s}</li>' for s in suggestions[:3])

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
  <div class="card-title">创作者周报 05.18–05.24</div>
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
editor_scripts = '\n'.join(s.replace("WEEK_TAG='W20'", "WEEK_TAG='W21'") for s in _w19_scripts)
print(f'  Editor/lang scripts extracted: {len(_w19_scripts)} blocks ({len(editor_scripts):,} chars)')

# Final HTML assembly
final_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>富途牛牛圈 创作者周报 2026-W21</title>
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

<div class="footer">富途牛牛圈 创作者运营周报 &nbsp;·&nbsp; 数据来源：q.futunn.com &nbsp;·&nbsp; 第21周 5/18–5/24 &nbsp;·&nbsp; 数据采集于 2026-05-25</div>
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
