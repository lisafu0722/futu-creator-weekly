"""Build W20 index.html: 26 priority cards with cs2 sections (data-driven)."""
import json, os, html

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, 'w20_priority26_data.json'), encoding='utf-8'))

FTYPE_MAP = {1:'原创帖',3:'转发',4:'文章',5:'股票评论',6:'评论',7:'问答',8:'问答',9:'视频',10:'调仓',11:'投票'}
WEEKDAYS = ['周一','周二','周三','周四','周五','周六','周日']

def fmt_num(n):
    n = int(n or 0)
    if n >= 10000: return f'{n/10000:.1f} 万'.replace('.0 ','')
    return f'{n:,}'

def fmt_int(n):
    return f'{int(n or 0):,}'

def feed_url(fid): return f'https://q.futunn.com/feed/{fid}'

def stock_url(name, code=''):
    if code: return f'https://www.futunn.com/stock/{code}'
    return f'https://www.futunn.com/quote/search?keyword={name}'

def esc(s): return html.escape(s or '', quote=True)

def gen_card(uid, k, idx):
    posts = k.get('posts', [])
    nick = k.get('nick', f'用户{uid}')
    pc = k.get('post_count', 0)
    tb, tl, tc, ts = k.get('browse',0), k.get('like',0), k.get('comment',0), k.get('share',0)
    # tier
    tier = 'tier-hi' if tb >= 1_000_000 else 'tier-mid' if tb >= 100_000 else 'tier-lo'

    # active days analysis
    days = sorted({p['date'][:10] for p in posts if p.get('date')})
    day_count = len(days)

    # weekday set
    wds = sorted({WEEKDAYS[(int(p['ts'])//86400 + 4) % 7] for p in posts if p.get('ts')})

    # time range
    times = sorted([p['date'][11:16] for p in posts if p.get('date') and len(p.get('date',''))>=16])
    time_range = f'{times[0]}–{times[-1]}' if times else '—'

    # content type spread
    type_count = {}
    for p in posts:
        t = FTYPE_MAP.get(p.get('ftype',0), f"类型{p.get('ftype',0)}")
        type_count[t] = type_count.get(t,0)+1
    type_summary = '、'.join([f'{t} {n}' for t,n in sorted(type_count.items(), key=lambda x:-x[1])][:3])

    # peaks: top by browse, like, comment, share
    def top(metric):
        if not posts: return None
        return max(posts, key=lambda p: (p.get(metric,0), -p.get('ts',0)))
    p_browse = top('browse')
    p_like = top('like')
    p_comment = top('comment')
    p_share = top('share')

    def peak_html(label, val, post, alt=False):
        cls = 'cs2-peak alt' if alt else 'cs2-peak'
        if not post or val == 0:
            return f'<div class="{cls}"><span class="cs2-peak-l">{label}</span> <span class="cs2-peak-v">—</span><span class="cs2-peak-t muted">本周无数据</span></div>'
        title = post.get('title') or '（无标题）'
        title_short = title if len(title) <= 24 else title[:23]+'…'
        return f'<div class="{cls}"><span class="cs2-peak-l">{label}</span> <span class="cs2-peak-v">{fmt_int(val)}</span><a class="cs2-peak-t" href="{feed_url(post["fid"])}" target="_blank">《{esc(title_short)}》</a></div>'

    # chips
    chips_html = ''
    if pc == 0:
        chips_html = '<span class="cs2-chip">📝 本周 <b>0</b> 篇发文</span>'
    else:
        chips_html += f'<span class="cs2-chip">📝 发文 <b>{pc}</b> 篇（{esc(type_summary)}）</span>'
        chips_html += f'<span class="cs2-chip">📅 {day_count}/7 天活跃</span>'
        if times:
            chips_html += f'<span class="cs2-chip">⏰ {esc(time_range)}</span>'
        chips_html += f'<span class="cs2-chip">👁 总浏览 <b>{fmt_num(tb)}</b></span>'

    # peaks
    if pc == 0:
        peaks_html = '<div class="cs2-peak"><span class="cs2-peak-l">本周</span> <span class="cs2-peak-v">未发文</span><span class="cs2-peak-t muted">建议查看上周内容并恢复更新</span></div>'
        peaks_grid_style = ''
    else:
        peaks_html = (
            peak_html('👁 浏览', p_browse.get('browse',0) if p_browse else 0, p_browse) +
            peak_html('👍 点赞', p_like.get('like',0) if p_like else 0, p_like) +
            peak_html('💬 评论', p_comment.get('comment',0) if p_comment else 0, p_comment, alt=True) +
            peak_html('🔁 转发', p_share.get('share',0) if p_share else 0, p_share, alt=True)
        )

    # cs2 pattern (3 insights — data-driven scaffolding for owner editing)
    if pc == 0:
        insights = f'''
      <div class="cs2-insight">
        <div class="cs2-insight-h">📭 本周状态</div>
        <div class="cs2-insight-b">本周（5/11–5/17）<b>暂无原创内容</b>。建议跟进创作者了解情况：是否在休假、有无内容规划、是否需要选题支持？</div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">💡 可主动提供的支持</div>
        <div class="cs2-insight-b">
          <ul>
            <li>分享本周市场热点（中美会面 / 美联储换届 / 半导体回调 / 港股IPO 拓璞·驭势·丹诺医药）作为选题切入点</li>
            <li>询问是否需要素材支持或推荐位资源</li>
            <li>了解是否有未发布的草稿，协助安排发布节奏</li>
          </ul>
        </div>
      </div>'''
    else:
        # top post link
        tp = p_browse
        tp_title = tp.get('title','') if tp else ''
        tp_title_disp = (tp_title[:38]+'…') if len(tp_title) > 38 else tp_title
        # stocks
        all_stocks = []
        for p in posts:
            for s in p.get('stocks',[]):
                if s and s not in all_stocks:
                    all_stocks.append(s)
        stocks_summary = '、'.join(all_stocks[:5]) if all_stocks else '—'

        # avg metrics
        avg_b = tb // pc if pc else 0
        eng = (tl + tc + ts)
        eng_rate = (eng / tb * 100) if tb else 0

        # day pattern
        wd_str = ' / '.join(wds[:5])

        insights = f'''
      <div class="cs2-insight">
        <div class="cs2-insight-h">🌟 本周亮点</div>
        <div class="cs2-insight-b">
          本周（5/11–5/17）共发布 <em>{pc}</em> 篇内容，<b>{day_count}/7 天活跃</b>。累计 <b>{fmt_num(tb)}</b> 浏览 · <b>{fmt_int(tl)}</b> 点赞 · <b>{fmt_int(tc)}</b> 评论 · <b>{fmt_int(ts)}</b> 转发。单篇阅读冠军：<a href="{feed_url(tp['fid']) if tp else '#'}" target="_blank">《{esc(tp_title_disp)}》</a> <em>{fmt_int(tp.get('browse',0)) if tp else 0}</em> 浏览。<b>篇均阅读 {fmt_int(avg_b)}</b>，互动率 {eng_rate:.2f}%。
        </div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">✅ 内容画像</div>
        <div class="cs2-insight-b">
          <ul>
            <li><b>内容类型</b>：{esc(type_summary)}</li>
            <li><b>发布节奏</b>：{esc(wd_str)}（共 {day_count} 天）{("，发布时段集中在 "+esc(time_range)) if times else ""}</li>
            <li><b>关注标的</b>：{esc(stocks_summary)}</li>
          </ul>
        </div>
      </div>
      <div class="cs2-insight">
        <div class="cs2-insight-h">💡 给您的反馈（待运营人员补充）</div>
        <div class="cs2-insight-b">
          <ul>
            <li>结合上方互动数据补充亮点 / 可优化点</li>
            <li>对比上周（W19）数据，标注趋势变化</li>
            <li>针对运营节奏 / 选题方向给出 1-2 条具体建议</li>
          </ul>
        </div>
      </div>'''

    # post list
    post_rows = ''
    for p in sorted(posts, key=lambda x: -x.get('ts',0)):
        title = p.get('title','') or '（无标题）'
        ftype_str = FTYPE_MAP.get(p.get('ftype',0), f"类型{p.get('ftype',0)}")
        ts_int = int(p.get('ts',0))
        wd = WEEKDAYS[(ts_int//86400 + 4) % 7]
        date_disp = p.get('date','')
        post_rows += f'''<div class="post-row">
  <span class="post-meta"><span class="post-date">{esc(date_disp)} {wd}</span><span class="badge">{ftype_str}</span></span>
  <a class="post-link" href="{feed_url(p['fid'])}" target="_blank">{esc(title)}</a>
  <span class="post-metrics">👁{fmt_int(p.get('browse',0))} &nbsp;👍{fmt_int(p.get('like',0))} &nbsp;💬{fmt_int(p.get('comment',0))} &nbsp;🔁{fmt_int(p.get('share',0))}</span>
</div>'''

    # stocks row
    stocks_row = ''
    seen = set()
    stock_chips = []
    for p in posts:
        for s in p.get('stocks',[]):
            if s and s not in seen:
                seen.add(s)
                stock_chips.append(f'<a class="stock-tag" href="{stock_url(s)}" target="_blank">{esc(s)}</a>')
    if stock_chips:
        stocks_row = f'<div class="stocks-row">关注标的：{"".join(stock_chips[:8])}</div>'

    # search blob (lower-cased nick for filter)
    search = esc((nick or '').lower())

    fans_disp = k.get('fans') or '—'
    fans_inline = f'👥 {fans_disp}' if k.get('fans') else f'👥 —'

    return f'''<div class="creator-card {tier}" data-uid="{uid}" data-posts="{pc}" data-views="{tb}" data-likes="{tl}" data-priority="{idx+1}" data-search="{search}">
  <div class="card-title">创作者周报 05.11–05.17</div>
  <div class="card-header">
    <div class="name-row">
      <a class="creator-name" href="https://q.futunn.com/profile/{uid}" target="_blank">{esc(nick)}</a>
      <span class="creator-uid">#{uid}</span>
      <span class="owner-tag">优先 · #{idx+1}</span>
      <span class="fans-inline">{esc(fans_inline)}</span>
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
      <div class="metric"><span class="num">{fmt_int(ts)}</span><span class="lbl">被转发</span></div>
    </div>
  </div>
  <div class="cs2">
    <div class="cs2-chips">{chips_html}</div>
    <div class="cs2-label">🏆 单篇峰值</div>
    <div class="cs2-peaks">{peaks_html}</div>
    <div class="cs2-pattern">
      <div class="cs2-pattern-title">📬 本周小结 · 给您的反馈</div>{insights}
    </div>
  </div>
  {stocks_row}
  <div class="card-disclaimer">上述內容由AI語言模型生成,僅供參考。以上內容不代表富途立場,不構成任何投資建議。</div>
  <details class="posts-detail">
    <summary>📋 查看全部帖子（{pc} 条）</summary>
    <div class="posts-list">{post_rows or "<div class='more-hint'>本周无内容</div>"}</div>
  </details>
</div>'''

# Build cards in priority order
cards_html = []
for idx, uid in enumerate(DATA['priority_uids_order']):
    k = DATA['creators'].get(str(uid))
    if not k:
        continue
    cards_html.append(gen_card(uid, k, idx))

cards_block = '\n'.join(cards_html)

# Read CSS from existing index.html
with open(os.path.join(ROOT, 'index.html'), encoding='utf-8') as f:
    src = f.read()
css_start = src.index('<style>')
css_end = src.index('</style>') + len('</style>')
css_block = src[css_start:css_end]

# JS for filter / sort / lang switching — keep minimal (search + sort)
js_block = '''
<script>
function filter(){
  const q=(document.getElementById('si').value||'').toLowerCase().trim();
  const sc=document.getElementById('sc');sc.style.display=q?'block':'none';
  let n=0;document.querySelectorAll('.creator-card').forEach(c=>{
    const m=!q||c.dataset.search.includes(q)||c.dataset.uid.includes(q);
    c.style.display=m?'':'none';if(m)n++;
  });
  document.getElementById('cl').textContent='显示 '+n+' 位';
}
function clearSearch(){document.getElementById('si').value='';filter();}
function resort(){
  const k=document.getElementById('ss').value;
  const grid=document.getElementById('grid');
  const cards=Array.from(grid.querySelectorAll('.creator-card'));
  cards.sort((a,b)=>{
    if(k==='priority')return (+a.dataset.priority)-(+b.dataset.priority);
    return (+b.dataset[k])-(+a.dataset[k]);
  });
  cards.forEach(c=>grid.appendChild(c));
}
</script>'''

html_out = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>富途牛牛圈 创作者周报 2026-W20</title>
{css_block}
</head>
<body>
<div class="hdr">
  <div class="hdr-badge">WEEK 20 · 2026</div>
  <h1>🐂 富途牛牛圈 创作者运营周报</h1>
  <div class="sub">2026 年第 20 周 &nbsp;·&nbsp; 5月11日（周一）— 5月17日（周日）</div>
  <div class="meta">数据采集于 2026-05-18 UTC+08:00 &nbsp;·&nbsp; 本期为 26 位优先 KOL（cs2 卡片，数据驱动版，运营人员可在浏览器内编辑反馈）</div>
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

<div class="overview-box">
  <h2>本期说明</h2>
  <div class="overview-p">
    <p>本期周报聚焦 <strong>26 位优先 KOL</strong>（含 W19 内测 9 位 + 新增 17 位）。每张卡片包含：本周内容统计、单篇峰值、内容画像。<br>
    <strong>📬 反馈区使用说明</strong>：橙色"📬 本周小结·给您的反馈"区域为运营人员手动编辑区，目前已自动填充数据画像，请运营人员根据 KOL 的内容质量、运营沟通情况，补充本周亮点 / 可优化建议后再发送给创作者。可直接在浏览器中点击文字开始编辑，编辑后状态会本地保存。</p>
  </div>
</div>

<div class="ctrl">
  <div class="search-wrap">
    <input type="text" id="si" placeholder="搜索创作者名称或 ID…" oninput="filter()">
    <button class="search-clear" id="sc" onclick="clearSearch()" title="清除搜索">✕</button>
  </div>
  <select id="ss" onchange="resort()">
    <option value="priority">按优先级排序</option>
    <option value="posts">按发帖数排序</option>
    <option value="views">按浏览量排序</option>
    <option value="likes">按点赞数排序</option>
  </select>
  <span class="cnt-lbl" id="cl">显示 26 位</span>
</div>

<div class="grid" id="grid">
{cards_block}
</div>

<div class="footer">富途牛牛圈 · 创作者运营周报 · 2026-W20 · 数据采集于 2026-05-18</div>
{js_block}
</body>
</html>
'''

out_path = os.path.join(ROOT, 'index.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html_out)
print(f'Wrote {out_path} ({len(html_out):,} bytes, {len(cards_html)} cards)')
