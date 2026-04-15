"""
周报生成 v2 - 含创作者小结、帖子跳转链接、顶部总周报
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json, os, re
from datetime import datetime, timezone, timedelta
from collections import Counter

TZ_HK = timezone(timedelta(hours=8))
script_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(script_dir, 'week_data_enriched.json'), encoding='utf-8') as f:
    data = json.load(f)

with open(os.path.join(script_dir, 'identity_data.json'), encoding='utf-8') as f:
    identity_data = json.load(f)

# 7个认证媒体号，顶部周报统计时剔除
MEDIA_UIDS = {'1162342', '5977079', '33792705', '28424063', '7388642', '17567706', '26294087'}

creators = data['creators']
all_uids = list(creators.keys())
non_media_creators = {uid: v for uid, v in creators.items() if uid not in MEDIA_UIDS}

# ===== 基础统计（口径：仅文章）=====
def get_articles(v):
    uid = str(v.get('uid', ''))
    return [p for p in v.get('posts', [])
            if p.get('feed_type_str') == '文章'
            and (not p.get('author_uid') or p.get('author_uid') == uid)]

def get_own_posts(uid, v):
    """返回创作者本人发布的所有帖子（过滤掉他人帖子）"""
    uid_str = str(uid)
    return [p for p in v.get('posts', [])
            if not p.get('author_uid') or p.get('author_uid') == uid_str]

total = len(all_uids)
# 活跃/未活跃 以是否有文章为准
active_creators_list = [(uid, v) for uid, v in creators.items() if len(get_articles(v)) > 0]
inactive_creators_list = [(uid, v) for uid, v in creators.items() if len(get_articles(v)) == 0]
active_creators_list.sort(key=lambda x: -len(get_articles(x[1])))

total_posts   = sum(len(get_articles(v)) for v in creators.values())
total_likes   = sum(v['total_likes'] for v in creators.values())
total_comments= sum(v['total_comments'] for v in creators.values())
total_views   = sum(v['total_views'] for v in creators.values())

days_order  = ['2026-04-06','2026-04-07','2026-04-08','2026-04-09','2026-04-10','2026-04-11','2026-04-12']
day_labels  = ['4/6(一)','4/7(二)','4/8(三)','4/9(四)','4/10(五)','4/11(六)','4/12(日)']
# 每日文章数（用于折线图和周报高峰统计）
daily_posts = {}
for uid, v in creators.items():
    for p in get_articles(v):
        daily_posts[p['date']] = daily_posts.get(p['date'], 0) + 1

type_totals = {'文章': total_posts}

# ===== 本周热议话题提取（从文章标题）=====
_TOPIC_STOP = {
    '一个','一下','一些','一次','什么','也是','不是','不了','今天','今日','本周','本文',
    '上周','分析','分享','介绍','关于','以及','可以','这个','这些','这里','那些','如何',
    '如果','对于','之后','之前','但是','还是','还有','就是','来看','目前','已经','所有',
    '需要','没有','不会','会有','看看','来说','可能','原来','因为','所以','而且','当然',
    '只有','后来','起来','大家','我们','他们','确实','主要','其实','非常','通过','方面',
    '情况','问题','影响','变化','数据','预期','超过','达到','创下','回调','下跌','上涨',
    '涨幅','跌幅','表现','背景','认为','公司','企业','发布','更新','内容','最新','近期',
    '宏观','今年','去年','下半','上半','季度','月份','周内','增长','下降','同比','环比',
    '重要','消息','关注','操作','策略','部署','复盘','笔记','记录','知道','看法','观点','展望',
    '港股','美股','市场','行情','投资','交易','估值','股票','全球','基金',
    # 媒体号模板词
    '深潮','链接','报道','作者','撰文','编译','根据','美东时间','日报','重要资讯',
    '昨日','推出','创始人','平台','设施','流出','突破','亿美元','万美元',
    '据官方','昨日总','总净','导读','昨日总净','万美元居','净流出','净流入',
    '详情','如下','原文','阅读','点击','转载','来源','表示','提到','近日','美元',
    # 截断噪声词
    '比特币现','以太坊现','火风分享','昨夜今晨','摩根士丹','股每日观',
    '正式上线','正式推出','轮融资','分析师','落幕了吗','如何卡位','利比特币','比特币或',
    '增长价值','达成停火','加密概念','韩国金融','全球资金','亿美元的','宣布退出','第二轮',
}

def _extract_topics():
    titles = []
    for uid, v in creators.items():
        for p in get_articles(v):
            t = p.get('title', '') or ''
            if t:
                titles.append(t)
    blob = ' '.join(titles)
    clean = re.sub(r'[@\$#＄]\S+|[A-Za-z0-9]+|[^\u4e00-\u9fa5\s]', ' ', blob)
    cnt = Counter(w for w in re.findall(r'[\u4e00-\u9fa5]{3,4}', clean)
                  if w not in _TOPIC_STOP)
    return [(w, n) for w, n in cnt.most_common(50) if n >= 3][:10]

# 全量股票提及（$符号显式打标口径）
# stock_vocab 供 gen_weekly_overview 读取 display name
stock_vocab = {}
all_stocks = Counter()
for uid, v in creators.items():
    for p in v['posts']:
        for s in p.get('stocks_mentioned', []):
            code = s['code']
            name = s['name']
            display = re.sub(r'[-]\s*[WSw]+$', '', name).strip()
            if code not in stock_vocab:
                stock_vocab[code] = {'display': display}
            all_stocks[code] += 1

# 最高互动帖子（全局 Top5）
all_posts_flat = []
for uid, v in creators.items():
    name = v.get('nick_name', f'用户{uid}')
    for p in v['posts']:
        all_posts_flat.append({'uid': uid, 'name': name, **p})
top_posts_global = sorted(all_posts_flat, key=lambda x: x['views'] + x['likes']*100 + x['comments']*200, reverse=True)[:5]

# ===== 内容小结生成 =====
def gen_creator_summary(uid, v):
    """为每位创作者生成一段文字小结"""
    posts = get_own_posts(uid, v)
    if not posts:
        return ''
    name = v.get('nick_name', f'用户{uid}')
    post_count = len(posts)
    active_days = sorted(set(p['date'] for p in posts))
    content_types = {}
    for p in posts:
        t = p['feed_type_str']
        content_types[t] = content_types.get(t, 0) + 1
    total_views_c = sum(p.get('views', 0) for p in posts)
    total_likes_c = sum(p.get('likes', 0) for p in posts)

    # 主要类型
    main_type = max(content_types, key=content_types.get) if content_types else ''
    other_types = {k: n for k, n in content_types.items() if k != main_type and n > 0}

    # 活跃节奏
    day_count = len(active_days)
    if day_count >= 7:
        rhythm = '全周每天均有发布，保持高频更新'
    elif day_count >= 5:
        rhythm = f'一周内 {day_count} 天活跃，发布较为规律'
    elif day_count >= 3:
        rhythm = f'本周在 {day_count} 天内集中发布'
    else:
        short_dates = '、'.join([d[-5:] for d in active_days])
        rhythm = f'仅在 {short_dates} 发布内容'

    # 主题词提取（从标题和文字中找高频词）
    all_text = ' '.join([(p.get('title') or '') + ' ' + p.get('text', '') for p in posts])
    # 去掉 @/$/# 标签后提取关键词
    clean_text = re.sub(r'[@$#]\S+', '', all_text)
    # 简单关键词：出现频率较高的名词片段
    keywords = Counter(re.findall(r'[\u4e00-\u9fa5]{2,4}', clean_text)).most_common(8)
    topic_words = [w for w, n in keywords if n >= 2 and w not in
                   ['评论', '转发', '关注', '分享', '更新', '今日', '发布', '内容', '市场', '投资', '行情']][:4]

    # 提及股票
    stock_counter = Counter()
    for p in posts:
        for s in p.get('stocks_mentioned', []):
            stock_counter[s['name']] += 1
    top_stocks = [s for s, _ in stock_counter.most_common(3)]

    # 互动
    best_post = max(posts, key=lambda p: p['likes'] + p['comments'] * 2 + p['views'] // 1000) if posts else None

    # 组织小结文字
    parts = []

    # 基本活跃描述
    if main_type == '文章':
        parts.append(f'本周共发布 {post_count} 篇文章，{rhythm}。')
    elif main_type == '转发帖':
        parts.append(f'本周共转发 {post_count} 条内容，{rhythm}。')
    elif main_type == '股票评论':
        parts.append(f'本周主要以股票评论形式活跃，共发布 {post_count} 条，{rhythm}。')
    else:
        parts.append(f'本周发布内容 {post_count} 条，{rhythm}。')

    # 内容类型多样性
    if other_types:
        other_str = '、'.join([f'{k} {n} 篇' for k, n in sorted(other_types.items(), key=lambda x: -x[1])])
        parts.append(f'内容形式包含{other_str}。')

    # 主题方向
    if topic_words:
        parts.append(f'内容主要围绕{"、".join(topic_words)}等话题展开。')
    elif top_stocks:
        parts.append(f'重点关注{"、".join(top_stocks[:2])}等标的。')

    # 股票提及
    if top_stocks and not topic_words:
        pass  # 已在上面提
    elif top_stocks:
        parts.append(f'频繁提及 {"、".join(top_stocks[:2])} 等。')

    # 互动表现
    if total_views_c >= 1_000_000:
        parts.append(f'总浏览量达 {total_views_c//10000:.0f} 万，传播效果突出。')
    elif total_views_c >= 100_000:
        parts.append(f'总浏览量 {total_views_c//10000:.1f} 万。')
    if total_likes_c >= 100:
        parts.append(f'获得 {total_likes_c} 次点赞，互动表现良好。')

    return ''.join(parts)

# ===== 总周报生成（全量创作者）=====
def gen_weekly_overview():
    """生成结构化本周总结，返回 HTML"""
    all_active = active_creators_list
    all_inactive_count = len(inactive_creators_list)
    active_count = len(all_active)
    active_rate = active_count / total * 100

    w_posts    = sum(len(get_articles(v)) for v in creators.values())
    w_views    = sum(v['total_views'] for v in creators.values())
    w_likes    = sum(v['total_likes'] for v in creators.values())
    w_comments = sum(v['total_comments'] for v in creators.values())

    peak_day_idx = max(range(len(days_order)), key=lambda i: daily_posts.get(days_order[i], 0))
    peak_day   = day_labels[peak_day_idx]
    peak_count = daily_posts.get(days_order[peak_day_idx], 0)
    hot_stocks_raw = [(c, n) for c, n in all_stocks.most_common(30) if stock_url(c)][:10]
    stock_rows = ''
    for rank, (code, n) in enumerate(hot_stocks_raw, 1):
        name = stock_vocab.get(code, {}).get('display', code)
        medal = {1:'🥇',2:'🥈',3:'🥉'}.get(rank, f'<span class="ov-rank">{rank}</span>')
        stock_rows += (
            f'<div class="ov-rank-row">'
            f'<span class="ov-medal">{medal}</span>'
            f'<a class="ov-rank-name" href="{stock_url(code)}" target="_blank">{esc(name)}</a>'
            f'<span class="ov-rank-val">{n} 次</span>'
            f'</div>'
        )

    personal_active = [(uid, v) for uid, v in all_active if uid not in MEDIA_UIDS]
    top10 = [(uid, v.get('nick_name', uid), len(get_articles(v)), v['total_views']) for uid, v in personal_active[:10]]
    top_view = max(personal_active, key=lambda x: x[1]['total_views'])
    top_view_uid  = top_view[0]
    top_view_name = top_view[1].get('nick_name', top_view[0])
    top_view_val  = top_view[1]['total_views']

    top5_rows = ''
    for rank, (uid, name, posts, views) in enumerate(top10, 1):
        medal = {1:'🥇',2:'🥈',3:'🥉'}.get(rank, f'<span class="ov-rank">{rank}</span>')
        top5_rows += (
            f'<div class="ov-rank-row">'
            f'<span class="ov-medal">{medal}</span>'
            f'<a class="ov-rank-name" href="https://q.futunn.com/profile/{uid}" target="_blank">{esc(name)}</a>'
            f'<span class="ov-rank-val">{posts}篇</span>'
            f'<span class="ov-rank-sub">{views//10000:.1f}万浏览</span>'
            f'</div>'
        )

    top_topics = _extract_topics()
    topic_tags_html = ''.join(
        f'<span class="topic-tag">{esc(w)}<span class="topic-cnt">{n}</span></span>'
        for w, n in top_topics
    )

    top_posts_html = ''
    for i, p in enumerate(top_posts_global):
        url = f'https://q.futunn.com/feed/{p["feed_id"]}'
        profile_url = f'https://q.futunn.com/profile/{p["uid"]}'
        display = p.get('title') or p.get('text', '')
        short = esc(display[:60] + ('…' if len(display) > 60 else ''))
        medal = {0:'🥇',1:'🥈',2:'🥉'}.get(i, f'<span class="ov-rank">{i+1}</span>')
        post_stocks = [s for s in p.get('stocks_mentioned', []) if stock_url(s['code'])][:3]
        post_stocks_html = ''.join(
            f'<a class="tp-stock" href="{stock_url(s["code"])}" target="_blank">{esc(s["name"].split("(")[0])}</a>'
            for s in post_stocks
        )
        top_posts_html += (
            f'<div class="tp-row">'
            f'<span class="ov-medal">{medal}</span>'
            f'<div class="tp-body">'
            f'<a class="tp-title" href="{url}" target="_blank">{short}</a>'
            f'<div class="tp-meta">'
            f'<a class="tp-author" href="{profile_url}" target="_blank">{esc(p["name"])}</a>'
            f'<span class="tp-stat">👁 {p["views"]:,}</span>'
            f'<span class="tp-stat">👍 {p["likes"]}</span>'
            f'<span class="tp-stat">💬 {p["comments"]}</span>'
            f'</div>'
            f'{"<div class=\"tp-stocks\">" + post_stocks_html + "</div>" if post_stocks_html else ""}'
            f'</div></div>'
        )

    return f'''
<div class="ov-kpi-row">
  <div class="ov-kpi-group">
    <div class="ov-kpi-label">创作者活跃</div>
    <div class="ov-kpi-pair">
      <div class="ov-kpi"><div class="ov-kpi-n">{active_count}<span class="ov-kpi-u">/{total}</span></div><div class="ov-kpi-l">活跃创作者</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{active_rate:.0f}<span class="ov-kpi-u">%</span></div><div class="ov-kpi-l">活跃率</div></div>
      <div class="ov-kpi ov-kpi-dim"><div class="ov-kpi-n">{all_inactive_count}</div><div class="ov-kpi-l">未活跃</div></div>
    </div>
  </div>
  <div class="ov-kpi-divider"></div>
  <div class="ov-kpi-group">
    <div class="ov-kpi-label">内容数据</div>
    <div class="ov-kpi-pair">
      <div class="ov-kpi"><div class="ov-kpi-n">{w_posts:,}</div><div class="ov-kpi-l">总发帖量</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{w_views//10000:.0f}<span class="ov-kpi-u">万</span></div><div class="ov-kpi-l">总浏览量</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{w_likes:,}</div><div class="ov-kpi-l">点赞</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{w_comments:,}</div><div class="ov-kpi-l">评论</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{round(w_posts/active_count,1) if active_count else 0}</div><div class="ov-kpi-l">均文章数</div></div>
    </div>
  </div>
</div>
<div class="ov-detail-row">
  <div class="ov-panel">
    <div class="ov-panel-title">📝 本周内容总结</div>
    <div class="ov-item"><span class="ov-icon">📈</span><span class="ov-item-l">发帖高峰</span><span class="ov-item-v">{esc(peak_day)} · {peak_count} 条</span></div>
    <div class="ov-item ov-item-note"><span class="ov-icon">💡</span><span class="ov-item-note-text">美伊停火谈判 + 霍尔木兹海峡危机升级引爆讨论；长光辰芯、群核科技双IPO申购；纳指七连涨、费城半导体创新高；香港稳定币牌照落地，市场热度集中爆发。</span></div>
    <div class="ov-topic-row">
      <div class="ov-topic-label">热议话题</div>
      <div class="ov-topic-tags">{topic_tags_html}</div>
    </div>
  </div>
  <div class="ov-panel">
    <div class="ov-panel-title">🔥 热门标的 Top 10</div>
    {stock_rows}
  </div>
  <div class="ov-panel">
    <div class="ov-panel-title">⭐ 发帖量 Top 10</div>
    {top5_rows}
    <div class="ov-rank-divider"></div>
    <div class="ov-item ov-item-extra"><span class="ov-icon">👁</span><span class="ov-item-l">最高浏览</span><a class="ov-item-link" href="https://q.futunn.com/profile/{top_view_uid}" target="_blank">{esc(top_view_name)}</a><span class="ov-item-v">&nbsp;{top_view_val//10000:.0f}万次</span></div>
    <div class="ov-footnote">仅展示个人号，不包含媒体号</div>
  </div>
  <div class="ov-panel ov-panel-wide">
    <div class="ov-panel-title">💬 本周高互动帖子 Top 5</div>
    {top_posts_html}
  </div>
</div>'''

# ===== HTML 组件 =====
def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def stock_url(code):
    """返回股票跳转 URL，无效/不可跳转的返回 None"""
    if not code:
        return None
    ticker = code.split('.')[0]
    # 纯指数（.SPX.US 等）
    if code.startswith('.'):
        return None
    # 外汇/差价合约
    if code.endswith('.FX') or code.endswith('.CFD'):
        return None
    # 期货主连、期权合约（ticker 含 main/current 或超长）
    tl = ticker.lower()
    if 'main' in tl or 'current' in tl or len(ticker) > 12:
        return None
    path = code.replace('.', '-')
    # HK 指数（800xxx.HK）
    if code.endswith('.HK') and ticker.startswith('8') and len(ticker) == 6:
        return f'https://www.futunn.com/index/{path}'
    return f'https://www.futunn.com/stock/{path}'

def gen_day_heatmap(active_days):
    days = ['04-06','04-07','04-08','04-09','04-10','04-11','04-12']
    day_names = ['一','二','三','四','五','六','日']
    html = '<div class="day-heatmap">'
    for i, day in enumerate(days):
        full_day = f'2026-{day}'
        active = full_day in active_days
        weekend = i >= 5
        cls = ('active' if active else 'inactive') + (' weekend-day' if weekend else '')
        html += f'<div class="day-cell {cls}" title="{full_day}">{day_names[i]}</div>'
    html += '</div>'
    return html

def gen_creator_card(uid, v):
    s_name = v.get('nick_name', f'用户{uid}')
    posts = get_articles(v)          # 只取原创文章
    own_posts = get_own_posts(uid, v)  # 本人全部帖子（互动数据和帖子列表）
    post_count = len(posts)
    active_days = sorted(set(p['date'] for p in posts)) if posts else []
    content_types = v.get('content_types', {})

    # 认证信息
    id_info = identity_data.get(uid, {})
    cert_wording = id_info.get('wording', '')
    is_media = uid in MEDIA_UIDS
    acct_type = 'media' if is_media else 'personal'
    if cert_wording:
        cert_html = f'<span class="cert-badge">{esc(cert_wording)}</span>'
    else:
        cert_html = ''

    summary_text = gen_creator_summary(uid, v)

    # 内容类型计数（本周内容模块）
    ct_articles = len(posts)  # 原创文章（author_uid == uid）
    ct_reposts = content_types.get('转发帖', 0)   # 转发其他文章

    # 互动数据：获得的转发数量
    total_s = sum(p.get('shares', 0) for p in own_posts)

    # 股票标签
    stock_counter = Counter()
    stock_code_map = {}
    for p in posts:
        for s in p.get('stocks_mentioned', []):
            stock_counter[s['name']] += 1
            stock_code_map[s['name']] = s['code']
    top_stocks = [(s, n) for s, n in stock_counter.most_common(10) if stock_url(stock_code_map.get(s, ''))][:3]
    stocks_html = ''
    if top_stocks:
        stock_spans = ''.join(
            f'<a class="stock-tag" href="{stock_url(stock_code_map[s])}" target="_blank">{esc(s)}</a>'
            for s, _ in top_stocks
        )
        stocks_html = f'<div class="stocks-row">关注标的：{stock_spans}</div>'

    # 指标（只计算本人帖子）
    total_v = sum(p.get('views', 0) for p in own_posts)
    total_l = sum(p.get('likes', 0) for p in own_posts)
    total_c = sum(p.get('comments', 0) for p in own_posts)
    day_count = len(active_days)
    engagement_score = total_l * 3 + total_c * 5 + total_v // 500
    fans_count = v.get('fans', 0)
    hist_posts = v.get('total_posts', 0)

    # 帖子列表（带链接）
    posts_list_html = ''
    for p in own_posts[:20]:
        feed_url = f'https://q.futunn.com/feed/{p["feed_id"]}'
        text = p.get('text', '')
        title = p.get('title', '')
        display = title or text
        display_short = esc(display[:70] + ('…' if len(display) > 70 else ''))
        wday_color = ' style="color:#e74c3c"' if p['weekday'] in ['周六','周日'] else ''
        type_badge = esc(p['feed_type_str'])
        has_img = '📷' if p.get('has_image') else ''
        posts_list_html += f'''<div class="post-row">
  <span class="post-meta">
    <span class="post-date"{wday_color}>{esc(p["datetime"])} {esc(p["weekday"])}</span>
    <span class="badge">{type_badge}</span>{has_img}
  </span>
  <a class="post-link" href="{feed_url}" target="_blank">{display_short}</a>
  <span class="post-metrics">👁{p["views"]:,} &nbsp;👍{p["likes"]} &nbsp;💬{p["comments"]}</span>
</div>'''
    if len(own_posts) > 20:
        posts_list_html += f'<div class="more-hint">…还有 {len(own_posts)-20} 条帖子</div>'

    # 代表帖
    if posts:
        best = max(posts, key=lambda p: p['likes'] * 3 + p['comments'] * 5 + p['views'] // 1000)
        best_url = f'https://q.futunn.com/feed/{best["feed_id"]}'
        best_display = best.get('title') or best.get('text', '')
        best_short = esc(best_display[:60] + ('…' if len(best_display) > 60 else ''))
        best_html = f'''<div class="best-post">
  <span class="best-label">代表帖：</span>
  <a href="{best_url}" target="_blank" class="best-link">{best_short}</a>
  <span class="best-metrics">👁{best["views"]:,} 👍{best["likes"]} 💬{best["comments"]}</span>
</div>'''
    else:
        best_html = ''

    return f'''<div class="creator-card" data-uid="{uid}" data-posts="{post_count}" data-views="{total_v}" data-likes="{total_l}" data-days="{day_count}" data-engagement="{engagement_score}" data-accttype="{acct_type}">
  <div class="card-header">
    <div class="name-row">
      <a class="creator-name" href="https://q.futunn.com/profile/{uid}" target="_blank">{esc(s_name)}</a>
      <span class="creator-uid">#{uid}</span>
      <span class="fans-inline">👥 {fans_count:,}</span>
      {cert_html}
    </div>
    <div class="active-days-line">本周活跃 <b>{day_count}/7</b> 天</div>
  </div>
  <div class="card-data-section">
    <div class="card-data-label">本周内容</div>
    <div class="metrics-row">
      <div class="metric"><span class="num">{ct_articles}</span><span class="lbl">原创文章</span></div>
    </div>
  </div>
  <div class="card-data-section">
    <div class="card-data-label">互动数据</div>
    <div class="metrics-row">
      <div class="metric"><span class="num">{total_v:,}</span><span class="lbl">浏览</span></div>
      <div class="metric"><span class="num">{total_l}</span><span class="lbl">获赞</span></div>
      <div class="metric"><span class="num">{total_c}</span><span class="lbl">评论</span></div>
      <div class="metric"><span class="num">{total_s}</span><span class="lbl">被转发</span></div>
    </div>
  </div>
  <div class="creator-summary">{summary_text}</div>
  {stocks_html}
  {best_html}
  <details class="posts-detail">
    <summary>📋 查看全部帖子（{post_count} 条）</summary>
    <div class="posts-list">{posts_list_html}</div>
  </details>
</div>'''

# ===== 图表（折线图）=====
W, H, PAD_L, PAD_R, PAD_T, PAD_B = 700, 140, 36, 20, 20, 28
counts = [daily_posts.get(d, 0) for d in days_order]
max_day = max(counts) or 1
n = len(counts)
def cx(i): return PAD_L + i * (W - PAD_L - PAD_R) / (n - 1)
def cy(v): return PAD_T + (1 - v / max_day) * (H - PAD_T - PAD_B)
pts = [(cx(i), cy(v)) for i, v in enumerate(counts)]
polyline_pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
fill_pts = f'{pts[0][0]:.1f},{H-PAD_B} ' + polyline_pts + f' {pts[-1][0]:.1f},{H-PAD_B}'
# 网格线 & y轴标注
grid_svg = ''
for gv in [0, max_day // 2, max_day]:
    gy = cy(gv)
    grid_svg += f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" stroke="#e8eaed" stroke-width="1"/>'
    grid_svg += f'<text x="{PAD_L-4}" y="{gy+3:.1f}" text-anchor="end" font-size="9" fill="#999">{gv}</text>'
# 数据点 + 标注
dots_svg = ''
for i, (x, y) in enumerate(pts):
    is_we = i >= 5
    color = '#b0bec5' if is_we else 'var(--p,#1565c0)'
    dots_svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" stroke="#fff" stroke-width="1.5"/>'
    dots_svg += f'<text x="{x:.1f}" y="{y-8:.1f}" text-anchor="middle" font-size="10" fill="#555" font-weight="600">{counts[i]}</text>'
# x轴标签
labels_svg = ''
for i, lbl in enumerate(day_labels):
    x = cx(i)
    labels_svg += f'<text x="{x:.1f}" y="{H:.1f}" text-anchor="middle" font-size="10" fill="#999">{lbl}</text>'

chart_svg = f'''<svg viewBox="0 0 {W} {H}" width="100%" style="display:block;max-width:{W}px;margin:0 auto;">
  {grid_svg}
  <polygon points="{fill_pts}" fill="rgba(21,101,192,0.08)"/>
  <polyline points="{polyline_pts}" fill="none" stroke="var(--p,#1565c0)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  {dots_svg}
  {labels_svg}
</svg>'''

# ===== 全局 Top5 帖子 =====
def gen_top_posts_table():
    rows = ''
    for i, p in enumerate(top_posts_global):
        url = f'https://q.futunn.com/feed/{p["feed_id"]}'
        display = p.get('title') or p.get('text', '')
        short = esc(display[:55] + ('…' if len(display) > 55 else ''))
        rows += f'''<tr>
  <td>{i+1}</td>
  <td><a href="https://q.futunn.com/profile/{p['uid']}" target="_blank">{esc(p['name'])}</a></td>
  <td><a href="{url}" target="_blank">{short}</a></td>
  <td>{p['views']:,}</td>
  <td>{p['likes']}</td>
  <td>{p['comments']}</td>
</tr>'''
    return rows

# ===== 未活跃创作者 =====
def gen_inactive():
    out = ''
    for uid, v in inactive_creators_list:
        name = esc(v.get('nick_name', f'用户{uid}'))
        out += f'<a class="inactive-chip" href="https://q.futunn.com/profile/{uid}" target="_blank">{name}</a>'
    return out

# ===== 完整 HTML =====
weekly_overview = gen_weekly_overview()

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>富途牛牛圈 创作者周报 2026-W14</title>
<style>
:root{{--p:#FF6900;--sec:#1a1a2e;--bg:#f5f7fa;--card:#fff;--bdr:#e8ecf0;--lt:#888;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:#333;font-size:14px;}}
a{{color:inherit;text-decoration:none;}}
a:hover{{text-decoration:underline;}}

/* 顶部 */
.hdr{{background:linear-gradient(135deg,#FF6900,#ff9800);color:#fff;padding:28px 24px 20px;text-align:center;}}
.hdr h1{{font-size:22px;font-weight:700;margin-bottom:4px;}}
.hdr .sub{{font-size:13px;opacity:.85;}}
.hdr .meta{{font-size:11px;opacity:.65;margin-top:4px;}}

/* 本周总结 */
.overview-box{{background:#fff;margin:16px 24px;border-radius:12px;padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,.06);max-width:1152px;margin-left:auto;margin-right:auto;}}
.overview-box h2{{font-size:15px;color:var(--sec);margin-bottom:12px;display:flex;align-items:center;gap:6px;}}
.overview-box h2::before{{content:'';display:inline-block;width:4px;height:16px;background:var(--p);border-radius:2px;}}
.overview-p{{font-size:13px;color:#444;}}
.overview-p strong{{color:var(--p);}}
/* KPI 行 - 分两组 */
.ov-kpi-row{{display:flex;gap:0;margin-bottom:16px;background:#f8fafc;border:1px solid var(--bdr);border-radius:12px;overflow:hidden;}}
.ov-kpi-group{{flex:1;padding:14px 16px;}}
.ov-kpi-group:first-child{{border-right:1px solid var(--bdr);}}
.ov-kpi-label{{font-size:11px;font-weight:600;color:var(--lt);text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px;}}
.ov-kpi-pair{{display:flex;gap:0;}}
.ov-kpi-divider{{width:1px;background:var(--bdr);}}
.ov-kpi{{flex:1;text-align:center;padding:4px 8px;border-right:1px solid var(--bdr);}}
.ov-kpi:last-child{{border-right:none;}}
.ov-kpi-n{{font-size:22px;font-weight:700;color:var(--p);line-height:1;}}
.ov-kpi-u{{font-size:12px;font-weight:400;}}
.ov-kpi-l{{font-size:10px;color:var(--lt);margin-top:3px;}}
.ov-kpi-dim .ov-kpi-n{{color:#90a4ae;}}
/* 四栏详情 */
.ov-detail-row{{display:grid;grid-template-columns:1.1fr 0.9fr 1.1fr 1.4fr;gap:12px;}}
.ov-panel-wide{{}}
.ov-panel{{background:#f8fafc;border-radius:10px;padding:14px 16px;border:1px solid var(--bdr);}}
.ov-panel-title{{font-size:13px;font-weight:600;color:var(--sec);margin-bottom:10px;padding-bottom:7px;border-bottom:2px solid var(--bdr);}}
.ov-item{{display:flex;align-items:flex-start;gap:5px;margin-bottom:8px;font-size:12px;line-height:1.5;}}
.ov-item:last-child{{margin-bottom:0;}}
.ov-icon{{font-size:13px;flex-shrink:0;margin-top:1px;}}
.ov-item-l{{color:var(--lt);white-space:nowrap;min-width:52px;flex-shrink:0;}}
.ov-item-v{{color:var(--sec);font-weight:500;}}
.ov-item-link{{color:var(--p);font-weight:500;}}
.ov-item-extra{{margin-top:8px;padding-top:8px;border-top:1px solid var(--bdr);}}
.ov-item-note{{background:#fffde7;border-radius:6px;padding:6px 8px;margin-top:4px;}}
.ov-item-note-text{{color:#6d4c00;font-size:11px;line-height:1.6;}}
/* 热门股票 */
.ov-stocks{{display:flex;flex-wrap:wrap;gap:7px;}}
.ov-stock{{background:#e8f0fe;color:#1967d2;padding:5px 12px;border-radius:6px;font-size:12px;font-weight:500;text-decoration:none;}}
.ov-stock:hover{{background:#1967d2;color:#fff;}}
/* 热议话题标签 */
.ov-topic-row{{margin-top:10px;}}
.ov-topic-label{{font-size:10px;font-weight:600;color:var(--lt);text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px;}}
.ov-topic-tags{{display:flex;flex-wrap:wrap;gap:5px;}}
.topic-tag{{background:#f0f4ff;color:#374785;font-size:12px;padding:4px 9px;border-radius:12px;display:inline-flex;align-items:center;gap:4px;}}
.topic-cnt{{font-size:10px;background:rgba(55,71,133,.15);padding:1px 5px;border-radius:6px;font-weight:700;}}
/* 排行 */
.ov-rank-row{{display:flex;align-items:center;gap:6px;margin-bottom:6px;font-size:12px;line-height:1.4;}}
.ov-medal{{font-size:14px;flex-shrink:0;width:20px;text-align:center;}}
.ov-rank{{width:18px;height:18px;border-radius:50%;background:#cfd8dc;color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;}}
.ov-rank-name{{flex:1;color:var(--sec);font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.ov-rank-val{{color:var(--p);font-weight:600;white-space:nowrap;}}
.ov-rank-sub{{color:var(--lt);font-size:10px;white-space:nowrap;}}
.ov-rank-divider{{border-top:1px solid var(--bdr);margin:8px 0;}}
.ov-footnote{{font-size:10px;color:#bbb;margin-top:8px;text-align:right;}}
/* 高互动帖子 */
.tp-row{{display:flex;align-items:flex-start;gap:6px;margin-bottom:10px;}}
.tp-row:last-child{{margin-bottom:0;}}
.tp-body{{flex:1;min-width:0;}}
.tp-title{{display:block;font-size:12px;color:var(--sec);font-weight:500;line-height:1.4;margin-bottom:3px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;}}
.tp-title:hover{{color:var(--p);}}
.tp-meta{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}}
.tp-author{{font-size:11px;color:var(--p);}}
.tp-stat{{font-size:11px;color:var(--lt);}}
.tp-stocks{{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px;}}
.tp-stock{{font-size:10px;background:#e8f0fe;color:#1967d2;padding:1px 6px;border-radius:4px;text-decoration:none;}}
.tp-stock:hover{{background:#1967d2;color:#fff;}}
@media(max-width:1100px){{.ov-detail-row{{grid-template-columns:1fr 1fr;}} }}
@media(max-width:700px){{.ov-kpi-row{{flex-direction:column;}} .ov-detail-row{{grid-template-columns:1fr;}} }}

/* 统计卡片 */
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;padding:0 24px 16px;max-width:1200px;margin:0 auto;}}
.sc{{background:#fff;border-radius:10px;padding:14px 8px;text-align:center;box-shadow:0 2px 6px rgba(0,0,0,.06);}}
.sc .n{{font-size:24px;font-weight:700;color:var(--p);line-height:1;}}
.sc .l{{font-size:11px;color:var(--lt);margin-top:4px;}}

/* 图表 */
.chart-sec{{background:#fff;border-radius:12px;padding:18px 20px;box-shadow:0 2px 8px rgba(0,0,0,.06);max-width:1152px;margin:0 auto 16px;}}
.chart-sec h3{{font-size:14px;color:var(--sec);margin-bottom:14px;}}
.chart-wrap{{overflow:hidden;}}

/* Top5 表格 */
.top5-sec{{background:#fff;border-radius:12px;padding:18px 20px;box-shadow:0 2px 8px rgba(0,0,0,.06);max-width:1152px;margin:0 auto 16px;}}
.top5-sec h3{{font-size:14px;color:var(--sec);margin-bottom:12px;}}
table{{width:100%;border-collapse:collapse;font-size:12px;}}
th{{text-align:left;padding:6px 10px;background:#f8f9fa;color:var(--lt);font-weight:500;border-bottom:1px solid var(--bdr);}}
td{{padding:7px 10px;border-bottom:1px solid var(--bdr);}}
td a{{color:var(--p);}}
tr:hover td{{background:#fef9f5;}}

/* 控制栏 */
.ctrl{{display:flex;flex-wrap:wrap;gap:8px;padding:0 24px 12px;max-width:1200px;margin:0 auto;align-items:center;}}
.ctrl input{{border:1px solid var(--bdr);border-radius:8px;padding:7px 12px;font-size:13px;outline:none;flex:1;min-width:180px;}}
.ctrl input:focus{{border-color:var(--p);}}
.ctrl select{{border:1px solid var(--bdr);border-radius:8px;padding:7px 10px;font-size:12px;background:#fff;outline:none;cursor:pointer;}}
.tabs{{display:flex;}}
.tab{{padding:7px 14px;border:1px solid var(--bdr);font-size:12px;cursor:pointer;background:#fff;color:var(--lt);}}
.tab:first-child{{border-radius:8px 0 0 8px;}}
.tab:last-child{{border-radius:0 8px 8px 0;border-left:none;}}
.tab.on{{background:var(--p);color:#fff;border-color:var(--p);}}
.cnt-lbl{{font-size:12px;color:var(--lt);margin-left:auto;}}

/* 卡片网格 */
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:14px;padding:0 24px 40px;max-width:1200px;margin:0 auto;}}
.creator-card{{background:var(--card);border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.06);border:1px solid var(--bdr);transition:box-shadow .2s;}}
.creator-card:hover{{box-shadow:0 4px 16px rgba(0,0,0,.11);}}
.card-header{{margin-bottom:10px;}}
.name-row{{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap;}}
.creator-name{{font-size:16px;font-weight:600;color:var(--sec);}}
.creator-name:hover{{color:var(--p);text-decoration:none;}}
.creator-uid{{font-size:10px;color:var(--lt);}}
.post-badge{{background:var(--p);color:#fff;font-size:11px;padding:2px 7px;border-radius:10px;font-weight:600;}}
.fans-inline{{font-size:11px;color:var(--lt);margin-left:2px;}}
.cert-badge{{background:#fff8e1;color:#e65100;font-size:10px;padding:2px 6px;border-radius:6px;border:1px solid #ffe082;white-space:nowrap;}}

/* 活跃天文字 */
.active-days-line{{font-size:11px;color:var(--lt);margin-top:4px;}}
.active-days-line b{{color:var(--p);font-weight:600;}}

/* 类型标签 */
.type-tags{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:0;}}
.tag{{background:#fff3e8;color:var(--p);font-size:11px;padding:2px 7px;border-radius:8px;}}
.tag b{{font-weight:700;}}

/* 指标行 */
.metrics-row{{display:flex;border:1px solid var(--bdr);border-radius:8px;overflow:hidden;margin:10px 0;}}
.metric{{flex:1;padding:7px 4px;text-align:center;border-right:1px solid var(--bdr);}}
.metric:last-child{{border-right:none;}}
.metric .num{{display:block;font-size:14px;font-weight:600;color:var(--sec);}}
.metric .lbl{{display:block;font-size:10px;color:var(--lt);margin-top:1px;}}
/* 卡片数据分区 */
.card-data-section{{margin:8px 0;}}
.card-data-label{{font-size:10px;font-weight:600;color:var(--lt);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px;}}
.card-data-section .metrics-row{{margin:0;}}

/* 创作者小结 */
.creator-summary{{font-size:12px;line-height:1.8;color:#555;background:#f8fafc;border-left:3px solid var(--p);padding:8px 10px;border-radius:0 6px 6px 0;margin-bottom:8px;}}

/* 股票 */
.stocks-row{{font-size:12px;color:var(--lt);margin-bottom:8px;}}
.stock-tag{{background:#e8f0fe;color:#1967d2;padding:1px 6px;border-radius:4px;margin:0 2px;font-size:11px;}}
.stock-tag:hover{{background:#1967d2;color:#fff;text-decoration:none;}}

/* 代表帖 */
.best-post{{background:#fafbfc;border-radius:6px;padding:7px 10px;font-size:12px;margin-bottom:8px;display:flex;flex-wrap:wrap;gap:4px;align-items:flex-start;border:1px solid var(--bdr);}}
.best-label{{color:var(--p);font-weight:600;white-space:nowrap;}}
.best-link{{flex:1;color:#333;min-width:0;word-break:break-all;}}
.best-link:hover{{color:var(--p);}}
.best-metrics{{white-space:nowrap;font-size:11px;color:var(--lt);}}

/* 帖子展开 */
.posts-detail{{margin-top:6px;}}
.posts-detail summary{{font-size:12px;color:var(--p);cursor:pointer;padding:4px 0;user-select:none;outline:none;}}
.posts-detail summary:hover{{opacity:.8;}}
.posts-list{{margin-top:8px;}}
.post-row{{display:flex;flex-wrap:wrap;align-items:flex-start;gap:5px;padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:12px;}}
.post-meta{{display:flex;align-items:center;gap:4px;flex-shrink:0;}}
.post-date{{color:var(--lt);font-size:11px;white-space:nowrap;}}
.badge{{background:#f0f0f0;color:#666;padding:1px 5px;border-radius:3px;font-size:10px;white-space:nowrap;}}
.post-link{{flex:1;color:#333;min-width:100px;word-break:break-all;}}
.post-link:hover{{color:var(--p);}}
.post-metrics{{white-space:nowrap;font-size:11px;color:var(--lt);}}
.more-hint{{font-size:11px;color:var(--lt);text-align:center;padding:6px;}}

/* 未活跃 */
.inactive-sec{{max-width:1200px;margin:0 auto 40px;padding:0 24px;}}
.inactive-sec h3{{font-size:14px;color:var(--lt);margin-bottom:10px;}}
.inactive-chips{{display:flex;flex-wrap:wrap;gap:6px;}}
.inactive-chip{{background:#fff;border:1px solid var(--bdr);border-radius:6px;padding:4px 10px;font-size:12px;color:#666;}}
.inactive-chip:hover{{border-color:var(--p);color:var(--p);text-decoration:none;}}

.hidden{{display:none!important;}}
.footer{{text-align:center;padding:14px;font-size:11px;color:var(--lt);border-top:1px solid var(--bdr);background:#fff;}}

@media(max-width:600px){{
  .grid,.ctrl,.stats{{padding-left:12px;padding-right:12px;}}
  .grid{{grid-template-columns:1fr;}}
  .overview-box{{margin-left:12px;margin-right:12px;}}
}}
</style>
</head>
<body>

<!-- 顶部标题 -->
<div class="hdr">
  <h1>🐂 富途牛牛圈 创作者运营周报</h1>
  <div class="sub">2026 年第 14 周 &nbsp;·&nbsp; 4月6日（周一）— 4月12日（周日）</div>
  <div class="meta">数据采集于 {data["collected_at"]} &nbsp;·&nbsp; 共纳入 {data["total_creators"]} 位创作者</div>
</div>

<!-- 本周总结 -->
<div class="overview-box">
  <h2>本周总结</h2>
  <div class="overview-p">{weekly_overview}</div>
</div>

<!-- 每日分布图 -->
<div class="chart-sec" style="padding:18px 24px;">
  <h3>📅 每日发帖分布</h3>
  <div class="chart-wrap">{chart_svg}</div>
</div>

<!-- 控制栏 -->
<div class="ctrl">
  <input type="text" id="si" placeholder="搜索创作者名称或 ID…" oninput="filter()">
  <select id="ss" onchange="resort()">
    <option value="posts">按发帖数排序</option>
    <option value="views">按浏览量排序</option>
    <option value="likes">按点赞数排序</option>
    <option value="days">按活跃天数排序</option>
    <option value="engagement">按互动分排序</option>
  </select>
  <div class="tabs">
    <button class="tab on" onclick="setTab('active',this)">活跃 ({len(active_creators_list)})</button>
    <button class="tab" onclick="setTab('inactive',this)">未发布 ({len(inactive_creators_list)})</button>
    <button class="tab" onclick="setTab('all',this)">全部</button>
  </div>
  <div class="tabs">
    <button class="tab on" onclick="setType('all',this)">全部账号</button>
    <button class="tab" onclick="setType('personal',this)">个人号</button>
    <button class="tab" onclick="setType('media',this)">媒体号</button>
  </div>
  <span class="cnt-lbl" id="cl">显示 {len(active_creators_list)} 位</span>
</div>

<!-- 创作者卡片 -->
<div class="grid" id="grid">
'''

for uid, v in active_creators_list:
    html += gen_creator_card(uid, v) + '\n'

html += f'''
</div>

<!-- 未活跃 -->
<div class="inactive-sec" id="inact" style="display:none">
  <h3>本周未发布内容（{len(inactive_creators_list)} 人）</h3>
  <div class="inactive-chips">{gen_inactive()}</div>
</div>

<div class="footer">富途牛牛圈 创作者运营周报 &nbsp;·&nbsp; 数据来源：q.futunn.com &nbsp;·&nbsp; 每周一自动更新</div>

<script>
let curTab='active', curType='all';
const cards=()=>Array.from(document.querySelectorAll('.creator-card'));

function filter(){{
  const q=document.getElementById('si').value.toLowerCase();
  let n=0;
  cards().forEach(c=>{{
    const nm=c.querySelector('.creator-name').textContent.toLowerCase();
    const id=c.querySelector('.creator-uid').textContent.toLowerCase();
    const matchQ=!q||nm.includes(q)||id.includes(q);
    const matchT=curTab==='all'?true:curTab==='active'?+c.dataset.posts>0:+c.dataset.posts===0;
    const matchType=curType==='all'?true:c.dataset.accttype===curType;
    c.classList.toggle('hidden',!(matchQ&&matchT&&matchType));
    if(matchQ&&matchT&&matchType) n++;
  }});
  document.getElementById('cl').textContent='显示 '+n+' 位';
  document.getElementById('inact').style.display=(curTab==='inactive'||curTab==='all')?'':'none';
}}

function setTab(t,el){{
  curTab=t;
  el.closest('.tabs').querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  filter();
}}

function setType(t,el){{
  curType=t;
  el.closest('.tabs').querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  filter();
}}

function resort(){{
  const k=document.getElementById('ss').value;
  const g=document.getElementById('grid');
  const cs=[...g.querySelectorAll('.creator-card')];
  cs.sort((a,b)=>{{
    const keys={{posts:'posts',views:'views',likes:'likes',days:'days',engagement:'engagement'}};
    return +b.dataset[keys[k]]-(+a.dataset[keys[k]]);
  }});
  cs.forEach(c=>g.appendChild(c));
}}
</script>
</body>
</html>'''

out_path = os.path.join(script_dir, 'weekly_report_2026W14.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"报告已生成: {out_path}")
print(f"文件大小: {len(html)//1024} KB")
