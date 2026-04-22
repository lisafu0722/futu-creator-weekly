"""
周报生成 v2 - 含创作者小结、帖子跳转链接、顶部总周报
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json, os, re
from datetime import datetime, timezone, timedelta
from collections import Counter
try:
    import anthropic as _anthropic
    _ai_client = _anthropic.Anthropic()
except Exception:
    _ai_client = None

TZ_HK = timezone(timedelta(hours=8))
script_dir = os.path.dirname(os.path.abspath(__file__))
_cached_ai_summary = ''
_cached_ai_topics = []

# 繁→简 映射，用于搜索时双向匹配
_T2S = {'來':'来','時':'时','這':'这','說':'说','學':'学','會':'会','財':'财','經':'经',
        '書':'书','點':'点','號':'号','發':'发','長':'长','機':'机','問':'问','電':'电',
        '從':'从','類':'类','對':'对','與':'与','國':'国','為':'为','個':'个','裡':'里',
        '後':'后','們':'们','過':'过','開':'开','關':'关','東':'东','實':'实','業':'业',
        '現':'现','進':'进','還':'还','動':'动','場':'场','強':'强','線':'线','見':'见',
        '體':'体','話':'话','將':'将','讓':'让','門':'门','間':'间','錢':'钱','劉':'刘',
        '張':'张','陳':'陈','趙':'赵','孫':'孙','馬':'马','韓':'韩','謝':'谢','鄭':'郑',
        '楊':'杨','黃':'黄','吳':'吴','鍾':'钟','許':'许','何':'何','盧':'卢','蔣':'蒋',
        '沈':'沈','韋':'韦','葉':'叶','彭':'彭','蕭':'萧','鄧':'邓','賴':'赖','魏':'魏',
        '錄':'录','視':'视','頻':'频','頭':'头','舊':'旧','歷':'历','義':'义','優':'优',
        '識':'识','購':'购','務':'务','達':'达','際':'际','總':'总','產':'产','資':'资',
        '數':'数','術':'术','處':'处','藝':'艺','應':'应','權':'权','樣':'样','規':'规',
        '歡':'欢','歸':'归','當':'当','裡':'里','裡':'里','帶':'带','幣':'币','帳':'账',
        '報':'报','幫':'帮','帥':'帅','師':'师','聽':'听','講':'讲','誰':'谁','認':'认',
        '論':'论','設':'设','試':'试','調':'调','請':'请','讀':'读','變':'变','費':'费',
        '貨':'货','貿':'贸','貸':'贷','賬':'账','賣':'卖','買':'买','負':'负','豐':'丰',
        '輛':'辆','輸':'输','轉':'转','邊':'边','遠':'远','選':'选','進':'进','連':'连',
        '週':'周','鐘':'钟','隻':'只','難':'难','雖':'虽','電':'电','雲':'云','頂':'顶',
        '題':'题','風':'风','飛':'飞','馳':'驰','驗':'验','髮':'发','高':'高','龍':'龙'}
_S2T = {v: k for k, v in _T2S.items() if v != k}

def _search_str(name):
    """生成包含简繁两种写法的搜索字符串"""
    to_simp = ''.join(_T2S.get(c, c) for c in name)
    to_trad = ''.join(_S2T.get(c, c) for c in name)
    return ' '.join({name, to_simp, to_trad}).lower()

with open(os.path.join(script_dir, 'week_data_enriched.json'), encoding='utf-8') as f:
    data = json.load(f)

with open(os.path.join(script_dir, 'identity_data.json'), encoding='utf-8') as f:
    identity_data = json.load(f)

with open(os.path.join(script_dir, 'profile_stats.json'), encoding='utf-8') as f:
    profile_stats = json.load(f)

# 7个认证媒体号，顶部周报统计时剔除
MEDIA_UIDS = {'1162342', '5977079', '33792705', '28424063', '7388642', '17567706', '26294087'}

# 跟进人 → UID 列表映射
OWNER_MAP = {
    'blakeli': {'11891989','7275545','31386762','23602671','7971272','10200673','2838770','15389198',
                '31303717','32607859','18641135','7780146','35153213','231491161','26391646','233869085',
                '13248499','34275720','33590692','35339163','33792705','28424063','28241713','31065447',
                '231575065','34123772','29795261','12604240','24989235','7388642','17567706','26294087',
                '5637519','231870570','32861462','232418329','5890381','12778176','234186329','26621837',
                '22059035','232787076','21036193','5263553','28806870','25547187','231135832','232726812',
                '12775482','3696648','26243689'},
    'chuiszewu': {'11341665','1162342','15522366','18932740','1894219','11283976','2869652','7117423',
                  '10604518','18218061','12313985','13503549','27747031','15816956','25914640','15765592',
                  '7483116','15822363','18437538','1065155','11578390','7149196','7045255','631978',
                  '165850','16997826','35143402','12107698','31505740','1499823','11884979','232965591',
                  '28353219','14639775','231506941','34125173','30481835','3226989','30385745'},
    'kristrawzeng': {'23462267','17296331','7223813','28650147','11351602','16751620','33748142','14405456',
                     '16565779','25169348','33984190','1513002','17813031','11350158','16459220','13298710',
                     '10203125','13340775','232846513','27027219','33294691','26056371','23597001','5995073',
                     '7625228','7004578','1409953','25481759','16712323','18799623','7198520','5950768',
                     '11995189','5579233','11364086','11922518','1472793','26938318','7474530','30752545',
                     '10219042','12089972','1158281','231866069','2845719','29747249','30936527','29817577',
                     '21257693','127715','18004503','2184566'},
    'lisafu': {'1132830','18953260','1160930','18031209','16134209','17491305','11292105','14657515',
               '124719','17693722','16564531','16891741','7493895','12623418','2854700','12178975',
               '11884113','1312525','5961921','5478250','29638625','12257686','14060116','16637818',
               '17981141','25484328','5977079','28841750','11297920','7926205','16428923','3351456',
               '32754839','1240288','29558645','7351896','35244821','15813386','15584643','12103405',
               '233127170','32796631'},
}
# UID → 跟进人 反查表
UID_TO_OWNER = {uid: owner for owner, uids in OWNER_MAP.items() for uid in uids}

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
    """返回创作者本人原创内容，严格对齐平台 /post/original（type=300）：
    author_uid==uid，且 feed_type 不是转发帖（2、3）。去重：同一 feed_id 只保留一条。"""
    uid_str = str(uid)
    seen, result = set(), []
    for p in v.get('posts', []):
        fid = p.get('feed_id', '')
        if fid and fid in seen:
            continue
        if fid:
            seen.add(fid)
        if ((not p.get('author_uid') or p.get('author_uid') == uid_str)
                and p.get('feed_type', 0) not in (2, 3)):
            result.append(p)
    return result

total = len(all_uids)
# 活跃/未活跃 以是否有本人发布的原创内容为准（等价于「原创」tab：author_uid == uid）
active_creators_list = [(uid, v) for uid, v in creators.items() if len(get_own_posts(uid, v)) > 0]
inactive_creators_list = [(uid, v) for uid, v in creators.items() if len(get_own_posts(uid, v)) == 0]
active_creators_list.sort(key=lambda x: -len(get_own_posts(x[0], x[1])))

total_posts   = sum(len(get_own_posts(uid, v)) for uid, v in creators.items())
total_likes   = sum(sum(p.get('likes',0)   for p in get_own_posts(uid, v)) for uid, v in creators.items())
total_comments= sum(sum(p.get('comments',0) for p in get_own_posts(uid, v)) for uid, v in creators.items())
total_views   = sum(sum(p.get('views',0)   for p in get_own_posts(uid, v)) for uid, v in creators.items())

_wk_names = ['一','二','三','四','五','六','日']
_sd = datetime.strptime(data['start_date'], '%Y-%m-%d')
_ed = datetime.strptime(data['end_date'],   '%Y-%m-%d')
days_order = [(_sd + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((_ed - _sd).days + 1)]
day_labels = [f'{(_sd+timedelta(days=i)).month}/{(_sd+timedelta(days=i)).day}({_wk_names[(_sd+timedelta(days=i)).weekday()]})' for i in range(len(days_order))]
# 每日文章数（用于折线图和周报高峰统计）
daily_posts = {}
for uid, v in creators.items():
    for p in get_own_posts(uid, v):
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
    """从帖子的 #话题# 标签中统计热议话题（作为 AI 提取失败时的兜底）"""
    topic_cnt = Counter()
    for uid, v in creators.items():
        for p in get_own_posts(uid, v):
            text = p.get('text', '') or ''
            for tag in re.findall(r'#([^#]{2,20})#', text):
                tag = tag.strip()
                if tag and tag not in _TOPIC_STOP:
                    topic_cnt[tag] += 1
    return [(w, n) for w, n in topic_cnt.most_common(50) if n >= 2][:12]

def _gen_ai_weekly_content():
    """用 Claude 一次调用生成本周总结 + 热议话题，返回 (summary_str, [(topic, count), ...])
    结果按周缓存到 report_stats.json，同一周重复生成报告时直接复用，不重调 API。"""
    week_key = data.get('week', '')
    cache_file = os.path.join(script_dir, 'report_stats.json')
    if os.path.exists(cache_file):
        try:
            with open(cache_file, encoding='utf-8') as f:
                cached = json.load(f)
            if cached.get('week') == week_key and cached.get('ai_summary'):
                summary = cached['ai_summary']
                topics = [(t, 0) for t in cached.get('ai_topics', [])]
                return summary, topics if topics else _extract_topics()
        except Exception:
            pass
    if not _ai_client:
        return '', _extract_topics()
    snippets = []
    for uid, v in creators.items():
        for p in get_own_posts(uid, v):
            title = (p.get('title') or '').strip()
            text  = (p.get('text')  or '').strip()
            s = title or text[:60]
            if s:
                snippets.append(s)
    if not snippets:
        return '', _extract_topics()
    sample = '\n'.join(snippets)
    start_str = data.get('start_date', '')
    end_str   = data.get('end_date', '')
    prompt = (
        f'以下是 {start_str} 至 {end_str} 期间，富途牛牛圈创作者发布的原创内容标题/摘要（共 {len(snippets)} 条）：\n\n'
        f'{sample}\n\n'
        '请完成两项任务，严格按以下格式输出，不要有其他文字：\n\n'
        'SUMMARY: 2-3句话（60-100字），总结本周内容覆盖的核心市场主题、热点事件和主要讨论方向。\n\n'
        'TOPICS: 话题1|话题2|话题3|话题4|话题5|话题6|话题7|话题8\n\n'
        '（TOPICS 为8-12个真实市场话题/板块/事件名，2-8字，用竖线分隔）'
    )
    try:
        msg = _ai_client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=400,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = msg.content[0].text.strip()
        summary, topics = '', []
        m_sum = re.search(r'SUMMARY[:：]\s*(.+?)(?=TOPICS|$)', raw, re.DOTALL)
        m_top = re.search(r'TOPICS[:：]\s*(.+)', raw, re.DOTALL)
        if m_sum:
            summary = m_sum.group(1).strip().replace('\n', '')
        if m_top:
            parts = [t.strip() for t in re.split(r'[|｜、,，]', m_top.group(1)) if t.strip()]
            topics = [(t, 0) for t in parts if 2 <= len(t) <= 10][:12]
        if not topics:
            topics = _extract_topics()
        return summary, topics
    except Exception as e:
        print(f'[AI content error] {e}')
        return '', _extract_topics()

# 全量股票提及（$符号显式打标口径）
# stock_vocab 供 gen_weekly_overview 读取 display name
stock_vocab = {}
all_stocks = Counter()
for uid, v in creators.items():
    for p in get_own_posts(uid, v):
        for s in p.get('stocks_mentioned', []):
            code = s['code']
            name = s['name']
            display = re.sub(r'[-]\s*[WSw]+$', '', name).strip()
            if code not in stock_vocab:
                stock_vocab[code] = {'display': display}
            all_stocks[code] += 1

# 点赞量 Top10（只取本人原创）
seen_feed_ids = set()
all_posts_flat = []
for uid, v in creators.items():
    name = v.get('nick_name', f'用户{uid}')
    for p in get_own_posts(uid, v):
        fid = p.get('feed_id')
        if fid and fid not in seen_feed_ids:
            seen_feed_ids.add(fid)
            all_posts_flat.append({'uid': uid, 'name': name, **p})
top_posts_global = sorted(all_posts_flat, key=lambda x: x['likes'], reverse=True)[:10]

# ===== 内容小结生成 =====
def gen_creator_summary(uid, v):
    """为每位创作者生成一段文字小结"""
    posts = get_own_posts(uid, v)
    if not posts:
        return ''
    active_days = sorted(set(p['date'] for p in posts))
    total_views_c = sum(p.get('views', 0) for p in posts)
    total_likes_c = sum(p.get('likes', 0) for p in posts)
    day_count = len(active_days)

    articles = [p for p in posts if p.get('feed_type_str') == '文章']

    # 活跃节奏
    if day_count >= 7:
        rhythm = '全周每天均有发布'
    elif day_count >= 5:
        rhythm = f'一周内 {day_count} 天活跃'
    elif day_count >= 3:
        rhythm = f'本周 {day_count} 天发布'
    else:
        short_dates = '、'.join([d[-5:] for d in active_days])
        rhythm = f'仅在 {short_dates} 发布'

    parts = []

    # 文章内容：直接引用标题 + 提及股票
    def _article_stocks(art_list):
        """汇总文章中提及的股票，返回最多3个名称"""
        sc = Counter()
        for a in art_list:
            for s in a.get('stocks_mentioned', []):
                sc[s['name']] += 1
        return [s for s, _ in sc.most_common(3)]

    if articles:
        n = len(articles)
        arts_by_time = sorted(articles, key=lambda p: p.get('timestamp', 0))
        art_stocks = _article_stocks(articles)
        stocks_clause = f'，涉及{"、".join(art_stocks)}等标的' if art_stocks else ''

        # 检查是否有 ai_summary 可用
        ai_summaries = [a.get('ai_summary', '') for a in arts_by_time]
        has_ai = any(s for s in ai_summaries)

        if n == 1:
            a = arts_by_time[0]
            title = (a.get('title') or a.get('text', ''))[:45]
            parts.append(f'本周发布 1 篇文章，{rhythm}。')
            if has_ai and ai_summaries[0]:
                parts.append(f'《{title}》：{ai_summaries[0]}')
                parts.append(f'浏览 {a["views"]:,}、获赞 {a["likes"]}。')
            elif title:
                parts.append(f'文章《{title}》{stocks_clause}，浏览 {a["views"]:,}、获赞 {a["likes"]}。')
        elif n <= 4:
            titles = '、'.join(
                f'《{(a.get("title") or a.get("text", ""))[:38]}》'
                for a in arts_by_time
            )
            parts.append(f'本周发布 {n} 篇文章，{rhythm}：{titles}。')
            if has_ai:
                # 合并各篇 ai_summary，用分号分隔
                combined = '；'.join(s for s in ai_summaries if s)
                if combined:
                    parts.append(combined)
            elif art_stocks:
                parts.append(f'涉及{"、".join(art_stocks)}等标的。')
        else:
            # 文章多时：前4篇标题 + ai_summary 或主题词
            titles = '、'.join(
                f'《{(a.get("title") or a.get("text", ""))[:30]}》'
                for a in arts_by_time[:4]
            )
            parts.append(f'本周发布 {n} 篇文章，{rhythm}，包括{titles}等。')
            if has_ai:
                # 取有摘要的前2篇合并
                combined = '；'.join(s for s in ai_summaries[:2] if s)
                if combined:
                    parts.append(combined)
            elif art_stocks:
                parts.append(f'涉及{"、".join(art_stocks)}等标的。')
            else:
                all_title_text = ' '.join((a.get('title') or '') for a in articles)
                clean_text = re.sub(r'[@$#]\S+', '', all_title_text)
                keywords = Counter(re.findall(r'[\u4e00-\u9fa5]{2,4}', clean_text)).most_common(8)
                topic_words = [w for w, c in keywords if c >= 2 and w not in _TOPIC_STOP][:3]
                if topic_words:
                    parts.append(f'内容涵盖{"、".join(topic_words)}等方向。')
    else:
        content_types = {}
        for p in posts:
            t = p['feed_type_str']
            content_types[t] = content_types.get(t, 0) + 1
        main_type = max(content_types, key=content_types.get) if content_types else ''
        if main_type == '转发帖':
            parts.append(f'本周转发 {len(posts)} 条内容，{rhythm}。')
        elif main_type == '股票评论':
            parts.append(f'本周以股票评论为主，共 {len(posts)} 条，{rhythm}。')
        else:
            parts.append(f'本周发布内容 {len(posts)} 条，{rhythm}。')

    # 最高互动文章（多于1篇时才单独点出）
    if len(articles) > 1:
        best = max(articles, key=lambda p: p['likes'] * 3 + p['comments'] * 5 + p['views'] // 1000)
        best_title = (best.get('title') or best.get('text', ''))[:40]
        if best_title and best.get('views', 0) > 0:
            parts.append(f'最高互动：《{best_title}》（浏览 {best["views"]:,}、获赞 {best["likes"]}）。')

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

    w_posts    = sum(len(get_own_posts(uid, v)) for uid, v in creators.items())
    w_views    = sum(sum(p.get('views',0)    for p in get_own_posts(uid, v)) for uid, v in creators.items())
    w_likes    = sum(sum(p.get('likes',0)    for p in get_own_posts(uid, v)) for uid, v in creators.items())
    w_comments = sum(sum(p.get('comments',0) for p in get_own_posts(uid, v)) for uid, v in creators.items())

    # 跟进人分布统计
    owner_stats = {}
    for _owner_name in ['blakeli', 'chuiszewu', 'kristrawzeng', 'lisafu']:
        _uids = OWNER_MAP[_owner_name]
        _o_total   = len([uid for uid in all_uids if str(uid) in _uids])
        _o_active  = len([uid for uid, v in all_active if str(uid) in _uids])
        _o_posts        = sum(len(get_own_posts(uid, v)) for uid, v in creators.items() if str(uid) in _uids)
        _o_posts_personal = sum(len(get_own_posts(uid, v)) for uid, v in creators.items() if str(uid) in _uids and str(uid) not in MEDIA_UIDS)
        _o_posts_media    = sum(len(get_own_posts(uid, v)) for uid, v in creators.items() if str(uid) in _uids and str(uid) in MEDIA_UIDS)
        _o_views   = sum(sum(p.get('views',0)    for p in get_own_posts(uid, v)) for uid, v in creators.items() if str(uid) in _uids)
        _o_likes   = sum(sum(p.get('likes',0)    for p in get_own_posts(uid, v)) for uid, v in creators.items() if str(uid) in _uids)
        _o_comments= sum(sum(p.get('comments',0) for p in get_own_posts(uid, v)) for uid, v in creators.items() if str(uid) in _uids)
        owner_stats[_owner_name] = (_o_total, _o_active, _o_total - _o_active, _o_posts, _o_posts_personal, _o_posts_media, _o_views, _o_likes, _o_comments)

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
    top10 = [(uid, v.get('nick_name', uid), len(get_own_posts(uid, v)), sum(p.get('views',0) for p in get_own_posts(uid, v))) for uid, v in personal_active[:10]]
    top_view = max(personal_active, key=lambda x: sum(p.get('views',0) for p in get_own_posts(x[0], x[1])))
    top_view_uid  = top_view[0]
    top_view_name = top_view[1].get('nick_name', top_view[0])
    top_view_val  = sum(p.get('views',0) for p in get_own_posts(top_view[0], top_view[1]))

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

    ai_summary, top_topics = _gen_ai_weekly_content()
    global _cached_ai_summary, _cached_ai_topics
    _cached_ai_summary = ai_summary
    _cached_ai_topics = [t for t, _ in top_topics]
    topic_tags_html = ''.join(
        f'<span class="topic-tag">{esc(w)}{f"""<span class="topic-cnt">{n}</span>""" if n > 0 else ""}</span>'
        for w, n in top_topics
    )

    top_posts_html = ''
    for i, p in enumerate(top_posts_global):
        url = f'https://q.futunn.com/feed/{p["feed_id"]}'
        profile_url = f'https://q.futunn.com/profile/{p["uid"]}'
        display = p.get('title') or p.get('text', '')
        short = esc(display[:60] + ('…' if len(display) > 60 else ''))
        medal = {0:'🥇',1:'🥈',2:'🥉'}.get(i, f'<span class="ov-rank">{i+1}</span>')
        # 按帖内提及次数排序，次数相同取先出现的，取 top3
        _sm = p.get('stocks_mentioned', [])
        _seen_order, _cnt = {}, {}
        for idx, s in enumerate(_sm):
            c = s['code']
            if c not in _seen_order:
                _seen_order[c] = idx
                _cnt[c] = {'name': s['name'], 'code': c, 'count': 0}
            _cnt[c]['count'] += 1
        _sorted = sorted(_cnt.values(), key=lambda x: (-x['count'], _seen_order[x['code']]))
        # 按名称去重，同名只保留排名最前的
        _seen_names = set()
        post_stocks = []
        for _s in _sorted:
            if _s['name'] not in _seen_names:
                _seen_names.add(_s['name'])
                post_stocks.append(_s)
            if len(post_stocks) == 3:
                break
        post_stocks_html = ''.join(
            f'<a class="tp-stock" href="{stock_url(s["code"])}" target="_blank">{esc(s["name"].split("(")[0])}</a>'
            if stock_url(s['code']) else
            f'<span class="tp-stock tp-stock-plain">{esc(s["name"].split("(")[0])}</span>'
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
            f'<span class="tp-stat">🔁 {p["shares"]}</span>'
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
    <div class="ov-footnote">活跃指本周有发布原创内容</div>
  </div>
  <div class="ov-kpi-divider"></div>
  <div class="ov-kpi-group">
    <div class="ov-kpi-label">内容数据</div>
    <div class="ov-kpi-pair">
      <div class="ov-kpi"><div class="ov-kpi-n">{w_posts:,}</div><div class="ov-kpi-l">总原创内容数量</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{w_views//10000:.0f}<span class="ov-kpi-u">万</span></div><div class="ov-kpi-l">总浏览量</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{w_likes:,}</div><div class="ov-kpi-l">点赞</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{w_comments:,}</div><div class="ov-kpi-l">评论</div></div>
      <div class="ov-kpi"><div class="ov-kpi-n">{round(w_posts/active_count,1) if active_count else 0}</div><div class="ov-kpi-l">均文章数</div></div>
    </div>
  </div>
</div>
<div class="ov-owner-table-wrap">
  <div class="ov-owner-label">跟进人分布</div>
  <table class="ov-owner-table">
    <thead><tr>
      <th>跟进人</th><th>总人数</th><th>活跃</th><th>未发布</th><th>活跃率</th>
      <th>发帖</th><th>个人号</th><th>媒体号</th><th>浏览</th><th>点赞</th><th>评论</th>
    </tr></thead>
    <tbody>
    {''.join(f"""<tr>
      <td class="ov-ot-name">{n}</td>
      <td>{t}</td>
      <td><span class="ov-owner-active">{a}</span></td>
      <td><span class="ov-owner-inactive">{i}</span></td>
      <td>
        <div class="ov-ot-bar-wrap">
          <div class="ov-ot-bar"><div class="ov-ot-bar-fill" style="width:{round(a/t*100) if t else 0}%"></div></div>
          <span class="ov-ot-rate">{round(a/t*100) if t else 0}%</span>
        </div>
      </td>
      <td class="ov-ot-num">{ps}</td>
      <td class="ov-ot-num ov-ot-sub">{pp}</td>
      <td class="ov-ot-num ov-ot-sub">{pm}</td>
      <td class="ov-ot-num">{vw//10000:.1f}万</td>
      <td class="ov-ot-num">{lk}</td>
      <td class="ov-ot-num">{cm}</td>
    </tr>""" for n,(t,a,i,ps,pp,pm,vw,lk,cm) in owner_stats.items())}
    </tbody>
  </table>
</div>
<div class="ov-detail-row">
  <div class="ov-panel">
    <div class="ov-panel-title">📝 本周内容总结</div>
    {f'<div class="ov-item ov-item-note"><span class="ov-icon">💡</span><span class="ov-item-note-text">{esc(ai_summary)}</span></div>' if ai_summary else ''}
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
</div>'''

# ===== HTML 组件 =====
def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def stock_url(code):
    """返回股票跳转 URL，无效/不可跳转的返回 None"""
    if not code:
        return None
    suffix = code.rsplit('.', 1)[-1]          # 'US' / 'HK' / 'FX' ...
    ticker = code[:-(len(suffix) + 1)]        # everything before last dot
    # 外汇/差价合约
    if suffix in ('FX', 'CFD'):
        return None
    tl = ticker.lower()
    # 期货主连/当月合约（ticker 含 main/current）→ /futures/
    if 'main' in tl or 'current' in tl:
        return f'https://www.futunn.com/futures/{ticker.upper()}-{suffix}'
    # 纯指数（.DJI.US / .SPX.US 等，ticker 以 . 开头）→ /index/
    if ticker.startswith('.'):
        return f'https://www.futunn.com/index/{ticker}-{suffix}'
    # 超长 ticker（期权等）
    if len(ticker) > 12:
        return None
    path = f'{ticker}-{suffix}'
    # HK 指数（800xxx.HK）→ /index/
    if suffix == 'HK' and ticker.startswith('8') and len(ticker) == 6:
        return f'https://www.futunn.com/index/{path}'
    return f'https://www.futunn.com/stock/{path}'

def gen_day_heatmap(active_days):
    html = '<div class="day-heatmap">'
    for full_day in days_order:
        d = datetime.strptime(full_day, '%Y-%m-%d')
        active = full_day in active_days
        weekend = d.weekday() >= 5
        cls = ('active' if active else 'inactive') + (' weekend-day' if weekend else '')
        html += f'<div class="day-cell {cls}" title="{full_day}">{_wk_names[d.weekday()]}</div>'
    html += '</div>'
    return html

def gen_creator_card(uid, v):
    s_name = v.get('nick_name', f'用户{uid}')
    own_posts = get_own_posts(uid, v)  # 本人原创内容
    posts = get_articles(v)          # 文章类型（仅用于内容展示列表）
    post_count = len(own_posts)
    active_days = sorted(set(p['date'] for p in own_posts)) if own_posts else []
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
    ct_articles = len(own_posts)  # 本人全部原创内容（含转发帖）
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
    fans_count = v.get('fans') or profile_stats.get(uid, {}).get('fans', 0)
    hist_posts = v.get('total_posts', 0)

    # 帖子列表（带链接）
    posts_list_html = ''
    for p in sorted(own_posts, key=lambda x: x.get('timestamp', 0), reverse=True)[:20]:
        feed_url = f'https://q.futunn.com/feed/{p["feed_id"]}'
        text = p.get('text', '')
        title = p.get('title', '')
        display = title or text or ('（转发）' if p.get('feed_type_str') == '转发帖' else '（无内容）')
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
  <span class="post-metrics">👁{p["views"]:,} &nbsp;👍{p["likes"]} &nbsp;💬{p["comments"]} &nbsp;🔁{p["shares"]}</span>
</div>'''
    if len(own_posts) > 20:
        posts_list_html += f'<div class="more-hint">…还有 {len(own_posts)-20} 条帖子</div>'

    best_html = ''
    _tier = 'tier-hi' if day_count >= 5 else ('tier-mid' if day_count >= 3 else 'tier-lo')
    _owner = UID_TO_OWNER.get(str(uid), 'unknown')
    return f'''<div class="creator-card {_tier}" data-uid="{uid}" data-posts="{len(own_posts)}" data-views="{total_v}" data-likes="{total_l}" data-days="{day_count}" data-engagement="{engagement_score}" data-fans="{fans_count}" data-accttype="{acct_type}" data-owner="{_owner}" data-search="{esc(_search_str(s_name))}">
  <div class="card-header">
    <div class="name-row">
      <a class="creator-name" href="https://q.futunn.com/profile/{uid}" target="_blank">{esc(s_name)}</a>
      <span class="creator-uid">#{uid}</span>
      <span class="owner-tag">{_owner}</span>
      <span class="fans-inline">👥 {fans_count:,}</span>
      {cert_html}
    </div>
    <div class="active-days-line">本周活跃 <b>{day_count}/7</b> 天</div>
  </div>
  <div class="card-data-section">
    <div class="card-data-label">本周内容</div>
    <div class="metrics-row">
      <div class="metric"><span class="num">{ct_articles}</span><span class="lbl">原创内容</span></div>
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
    <summary>📋 查看全部帖子（{len(own_posts)} 条）</summary>
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
    grid_svg += f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4,3"/>'
    grid_svg += f'<text x="{PAD_L-6}" y="{gy+4:.1f}" text-anchor="end" font-size="10" fill="#94a3b8" font-family="PingFang SC,Microsoft YaHei,sans-serif">{gv}</text>'
# 数据点 + 标注
dots_svg = ''
for i, (x, y) in enumerate(pts):
    is_we = i >= 5
    dot_color = '#94a3b8' if is_we else '#FF6900'
    lbl_color = '#94a3b8' if is_we else '#0f172a'
    dots_svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{dot_color}" stroke="#fff" stroke-width="2"/>'
    dots_svg += f'<text x="{x:.1f}" y="{y-10:.1f}" text-anchor="middle" font-size="11" fill="{lbl_color}" font-weight="700" font-family="PingFang SC,Microsoft YaHei,sans-serif">{counts[i]}</text>'
# x轴标签
labels_svg = ''
for i, lbl in enumerate(day_labels):
    x = cx(i)
    is_we = i >= 5
    lc = '#94a3b8' if is_we else '#64748b'
    labels_svg += f'<text x="{x:.1f}" y="{H:.1f}" text-anchor="middle" font-size="11" fill="{lc}" font-family="PingFang SC,Microsoft YaHei,sans-serif">{lbl}</text>'

chart_svg = f'''<svg viewBox="0 0 {W} {H}" width="100%" style="display:block;max-width:{W}px;margin:0 auto;">
  <defs>
    <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FF6900" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#FF6900" stop-opacity="0.01"/>
    </linearGradient>
  </defs>
  {grid_svg}
  <polygon points="{fill_pts}" fill="url(#chartFill)"/>
  <polyline points="{polyline_pts}" fill="none" stroke="#FF6900" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  {dots_svg}
  {labels_svg}
</svg>'''

# ===== 点赞量 Top5 独立表格 =====
def gen_top_likes_section():
    rows = ''
    for i, p in enumerate(top_posts_global):
        url = f'https://q.futunn.com/feed/{p["feed_id"]}'
        profile_url = f'https://q.futunn.com/profile/{p["uid"]}'
        display = p.get('title') or p.get('text', '')
        short = esc(display[:45] + ('…' if len(display) > 45 else ''))
        medal = {0:'🥇',1:'🥈',2:'🥉'}.get(i, f'<b>{i+1}</b>')
        _sm = p.get('stocks_mentioned', [])
        _seen_order, _cnt = {}, {}
        for idx, s in enumerate(_sm):
            c = s['code']
            if c not in _seen_order:
                _seen_order[c] = idx
                _cnt[c] = {'name': s['name'], 'code': c, 'count': 0}
            _cnt[c]['count'] += 1
        _sorted = sorted(_cnt.values(), key=lambda x: (-x['count'], _seen_order[x['code']]))
        _seen_names, post_stocks = set(), []
        for _s in _sorted:
            if _s['name'] not in _seen_names:
                _seen_names.add(_s['name'])
                post_stocks.append(_s)
            if len(post_stocks) == 3:
                break
        stocks_cell = ' '.join(
            f'<a class="tp-stock" href="{stock_url(s["code"])}" target="_blank">{esc(s["name"].split("(")[0])}</a>'
            if stock_url(s['code']) else
            f'<span class="tp-stock tp-stock-plain">{esc(s["name"].split("(")[0])}</span>'
            for s in post_stocks
        )
        rows += f'''<tr>
  <td class="tl-rank">{medal}</td>
  <td><a href="{profile_url}" target="_blank" class="tl-author">{esc(p["name"])}</a></td>
  <td><a href="{url}" target="_blank" class="tl-content">{short}</a></td>
  <td class="tl-stocks-cell">{stocks_cell if stocks_cell else '<span style="color:var(--lt)">—</span>'}</td>
  <td class="tl-num">{p["views"]:,}</td>
  <td class="tl-num tl-likes">{p["likes"]}</td>
  <td class="tl-num">{p["comments"]}</td>
  <td class="tl-num">{p["shares"]}</td>
</tr>'''
    return f'''<div class="top5-sec">
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
    <tbody>{rows}</tbody>
  </table>
</div>'''

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
  <td>{p['shares']}</td>
</tr>'''
    return rows

# ===== 未活跃创作者 =====
def gen_inactive():
    out = ''
    for uid, v in inactive_creators_list:
        name = esc(v.get('nick_name', f'用户{uid}'))
        owner = UID_TO_OWNER.get(str(uid), 'unknown')
        acct_type = 'media' if str(uid) in MEDIA_UIDS else 'personal'
        out += f'<a class="inactive-chip" data-owner="{owner}" data-accttype="{acct_type}" href="https://q.futunn.com/profile/{uid}" target="_blank">{name}</a>'
    return out

# ===== 完整 HTML =====
weekly_overview = gen_weekly_overview()

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>富途牛牛圈 创作者周报 {data.get('week', '')}</title>
<style>
:root{{
  --p:#FF6900;--p-light:#fff3e8;--p-dark:#d45500;
  --sec:#0f172a;--sec2:#334155;
  --bg:#f1f5f9;--card:#fff;--bdr:#e2e8f0;--lt:#94a3b8;
  --blue:#3b82f6;--blue-light:#dbeafe;--blue-dark:#1d4ed8;
  --sh:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);
  --sh-md:0 4px 12px rgba(0,0,0,.07),0 2px 4px rgba(0,0,0,.05);
  --sh-lg:0 12px 24px rgba(0,0,0,.09),0 4px 8px rgba(0,0,0,.06);
  --r:14px;--r-sm:10px;--r-xs:6px;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:#1e293b;font-size:14px;-webkit-font-smoothing:antialiased;}}
a{{color:inherit;text-decoration:none;}}
a:hover{{text-decoration:underline;}}

/* ── Header ── */
.hdr{{
  background:linear-gradient(135deg,#0f172a 0%,#1e293b 55%,#1a1a2e 100%);
  color:#fff;padding:36px 24px 28px;text-align:center;
  border-bottom:3px solid var(--p);position:relative;overflow:hidden;
}}
.hdr::before{{
  content:'';position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(ellipse 80% 55% at 50% 115%,rgba(255,105,0,.2) 0%,transparent 70%);
}}
.hdr-badge{{
  display:inline-block;background:rgba(255,105,0,.2);color:#ffb07a;
  border:1px solid rgba(255,105,0,.35);border-radius:20px;
  padding:3px 14px;font-size:11px;font-weight:700;margin-bottom:10px;letter-spacing:.8px;position:relative;
}}
.hdr h1{{font-size:32px;font-weight:700;margin-bottom:6px;letter-spacing:.2px;position:relative;}}
.hdr .sub{{font-size:14px;opacity:.82;position:relative;}}
.hdr .meta{{font-size:11px;opacity:.45;margin-top:6px;position:relative;}}

/* ── Overview box ── */
.overview-box{{
  background:var(--card);margin:20px auto;border-radius:var(--r);
  padding:22px 26px;box-shadow:var(--sh-md);max-width:1160px;border:1px solid var(--bdr);
}}
.overview-box h2{{font-size:15px;color:var(--sec);margin-bottom:14px;display:flex;align-items:center;gap:8px;}}
.overview-box h2::before{{
  content:'';display:inline-block;width:4px;height:18px;border-radius:2px;
  background:linear-gradient(180deg,var(--p),var(--p-dark));
}}
.overview-p{{font-size:13px;color:#475569;}}
.overview-p strong{{color:var(--p);}}

/* ── KPI row ── */
.ov-kpi-row{{display:flex;gap:12px;margin-bottom:16px;}}
.ov-kpi-group{{
  flex:1;padding:16px 18px;border-radius:12px;border:1px solid var(--bdr);
  background:linear-gradient(145deg,#fafbfc 0%,#fff 100%);
}}
.ov-kpi-group:first-child{{border-top:3px solid var(--p);}}
.ov-kpi-group:last-child{{border-top:3px solid var(--blue);}}
.ov-kpi-label{{font-size:10px;font-weight:700;color:var(--lt);text-transform:uppercase;letter-spacing:.8px;margin-bottom:12px;}}
.ov-kpi-pair{{display:flex;gap:0;}}
.ov-kpi-divider{{width:1px;background:var(--bdr);}}
.ov-owner-table-wrap{{padding:0 24px 16px;max-width:1200px;margin:0 auto;}}
.ov-owner-label{{font-size:10px;font-weight:700;color:var(--lt);text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px;}}
.ov-owner-table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden;}}
.ov-owner-table th{{background:#f8fafc;font-size:11px;font-weight:600;color:var(--lt);text-align:center;padding:8px 12px;border-bottom:1px solid var(--bdr);}}
.ov-owner-table th:first-child{{text-align:left;}}
.ov-owner-table td{{padding:10px 12px;border-bottom:1px solid #f1f5f9;text-align:center;color:#334155;}}
.ov-owner-table tr:last-child td{{border-bottom:none;}}
.ov-owner-table tbody tr:hover{{background:#f8fafc;}}
.ov-ot-name{{font-weight:700;color:var(--sec);text-align:left!important;}}
.ov-ot-num{{font-weight:600;}}
.ov-owner-active{{font-size:12px;color:#16a34a;background:#dcfce7;padding:2px 8px;border-radius:10px;font-weight:600;}}
.ov-owner-inactive{{font-size:12px;color:#dc2626;background:#fee2e2;padding:2px 8px;border-radius:10px;font-weight:600;}}
.ov-ot-bar-wrap{{display:flex;align-items:center;gap:6px;justify-content:center;}}
.ov-ot-bar{{width:60px;height:5px;background:#e2e8f0;border-radius:3px;flex-shrink:0;}}
.ov-ot-bar-fill{{height:100%;background:#22c55e;border-radius:3px;}}
.ov-ot-rate{{font-size:11px;color:var(--lt);white-space:nowrap;}}
.ov-ot-sub{{color:#94a3b8!important;font-weight:400!important;font-size:12px;}}
.ov-kpi{{flex:1;text-align:center;padding:4px 10px;border-right:1px solid var(--bdr);}}
.ov-kpi:last-child{{border-right:none;}}
.ov-kpi-n{{font-size:28px;font-weight:700;color:var(--sec);line-height:1;}}
.ov-kpi-u{{font-size:13px;font-weight:400;color:var(--sec2);}}
.ov-kpi-l{{font-size:10px;color:var(--lt);margin-top:4px;font-weight:500;}}
.ov-kpi-group:first-child .ov-kpi-n{{color:var(--p);}}
.ov-kpi-group:last-child .ov-kpi-n{{color:var(--blue-dark);}}
.ov-kpi-dim .ov-kpi-n{{color:#cbd5e1 !important;}}

/* ── Detail panels ── */
.ov-detail-row{{display:grid;grid-template-columns:1.1fr 0.9fr 1.1fr;gap:12px;}}
.ov-panel{{background:#fafbfc;border-radius:10px;padding:14px 16px;border:1px solid var(--bdr);}}
.ov-panel-title{{font-size:11px;font-weight:700;color:var(--sec2);margin-bottom:10px;padding-bottom:7px;border-bottom:1px solid var(--bdr);text-transform:uppercase;letter-spacing:.5px;}}
.ov-item{{display:flex;align-items:flex-start;gap:5px;margin-bottom:8px;font-size:12px;line-height:1.5;}}
.ov-item:last-child{{margin-bottom:0;}}
.ov-icon{{font-size:13px;flex-shrink:0;margin-top:1px;}}
.ov-item-l{{color:var(--lt);white-space:nowrap;min-width:52px;flex-shrink:0;}}
.ov-item-v{{color:var(--sec);font-weight:500;}}
.ov-item-link{{color:var(--p);font-weight:500;}}
.ov-item-extra{{margin-top:8px;padding-top:8px;border-top:1px solid var(--bdr);}}
.ov-item-note{{background:#fff8f0;border-radius:6px;padding:6px 8px;margin-top:4px;border-left:2px solid var(--p);}}
.ov-item-note-text{{color:#7c3a00;font-size:11px;line-height:1.6;}}

/* ── Hot stocks ── */
.ov-stocks{{display:flex;flex-wrap:wrap;gap:6px;}}
.ov-stock{{
  background:linear-gradient(135deg,#eff6ff,#dbeafe);color:#1d4ed8;
  padding:4px 12px;border-radius:20px;font-size:11px;font-weight:600;
  border:1px solid #bfdbfe;transition:all .15s;
}}
.ov-stock:hover{{background:linear-gradient(135deg,#1d4ed8,#2563eb);color:#fff;border-color:transparent;text-decoration:none;}}

/* ── Topic tags ── */
.ov-topic-row{{margin-top:10px;}}
.ov-topic-label{{font-size:10px;font-weight:700;color:var(--lt);text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px;}}
.ov-topic-tags{{display:flex;flex-wrap:wrap;gap:5px;}}
.topic-tag{{
  background:linear-gradient(135deg,#f0f4ff,#e8edff);color:#3730a3;
  font-size:11px;padding:4px 10px;border-radius:12px;border:1px solid #c7d2fe;
  display:inline-flex;align-items:center;gap:4px;transition:all .15s;cursor:default;
}}
.topic-tag:hover{{background:linear-gradient(135deg,#3730a3,#4338ca);color:#fff;border-color:transparent;}}
.topic-cnt{{font-size:10px;background:rgba(55,48,163,.15);padding:1px 5px;border-radius:6px;font-weight:700;}}

/* ── Ranking ── */
.ov-rank-row{{display:flex;align-items:center;gap:6px;margin-bottom:7px;font-size:12px;line-height:1.4;}}
.ov-medal{{font-size:15px;flex-shrink:0;width:22px;text-align:center;}}
.ov-rank{{width:20px;height:20px;border-radius:50%;background:#94a3b8;color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;}}
.ov-rank-name{{flex:1;color:var(--sec);font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.ov-rank-val{{color:var(--p);font-weight:700;white-space:nowrap;}}
.ov-rank-sub{{color:var(--lt);font-size:10px;white-space:nowrap;}}
.ov-rank-divider{{border-top:1px dashed var(--bdr);margin:8px 0;}}
.ov-footnote{{font-size:10px;color:#cbd5e1;margin-top:8px;text-align:right;}}

/* ── Top posts ── */
.tp-row{{display:flex;align-items:flex-start;gap:8px;margin-bottom:11px;padding-bottom:10px;border-bottom:1px solid var(--bdr);}}
.tp-row:last-child{{margin-bottom:0;padding-bottom:0;border-bottom:none;}}
.tp-body{{flex:1;min-width:0;}}
.tp-title{{display:block;font-size:12px;color:var(--sec);font-weight:600;line-height:1.45;margin-bottom:4px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;}}
.tp-title:hover{{color:var(--p);text-decoration:none;}}
.tp-meta{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}}
.tp-author{{font-size:11px;color:var(--p);font-weight:500;}}
.tp-stat{{font-size:11px;color:var(--lt);}}
.tp-stocks{{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px;}}
.tp-stock{{font-size:10px;background:#dbeafe;color:#1d4ed8;padding:2px 8px;border-radius:12px;font-weight:500;transition:all .15s;}}
.tp-stock:hover{{background:#1d4ed8;color:#fff;text-decoration:none;}}
.tp-stock-plain{{font-size:10px;background:#f1f5f9;color:#64748b;padding:2px 8px;border-radius:12px;}}

@media(max-width:1100px){{.ov-detail-row{{grid-template-columns:1fr 1fr;}}}}
@media(max-width:700px){{.ov-kpi-row{{flex-direction:column;}} .ov-detail-row{{grid-template-columns:1fr;}}}}

/* ── Chart ── */
.chart-sec{{background:var(--card);border-radius:var(--r);padding:20px 24px;box-shadow:var(--sh-md);max-width:1160px;margin:0 auto 16px;border:1px solid var(--bdr);}}
.chart-sec h3{{font-size:14px;font-weight:600;color:var(--sec);margin-bottom:16px;}}
.chart-wrap{{overflow:hidden;}}

/* ── Table ── */
.top5-sec{{background:var(--card);border-radius:var(--r);padding:20px 24px;box-shadow:var(--sh-md);max-width:1160px;margin:0 auto 16px;border:1px solid var(--bdr);}}
.top5-sec h3{{font-size:14px;font-weight:600;color:var(--sec);margin-bottom:14px;}}
table{{width:100%;border-collapse:collapse;font-size:12px;}}
th{{text-align:left;padding:8px 10px;background:#f8fafc;color:var(--lt);font-weight:700;border-bottom:2px solid var(--bdr);font-size:10px;text-transform:uppercase;letter-spacing:.4px;}}
td{{padding:8px 10px;border-bottom:1px solid var(--bdr);color:#334155;}}
td a{{color:var(--p);}}
tr:last-child td{{border-bottom:none;}}
tr:hover td{{background:#fef9f5;}}

/* ── Top likes table ── */
.tl-rank{{text-align:center;font-size:16px;width:44px;}}
.tl-author{{color:var(--p);font-weight:600;white-space:nowrap;}}
.tl-author:hover{{text-decoration:underline;}}
.tl-content{{color:var(--sec);font-weight:500;line-height:1.5;display:block;}}
.tl-content:hover{{color:var(--p);text-decoration:none;}}
.tl-stocks{{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px;}}
.tl-stocks-cell{{vertical-align:middle;}}
.tl-num{{text-align:right;white-space:nowrap;color:#334155;}}
.tl-likes{{color:var(--p);font-weight:700;}}

/* ── Controls ── */
.ctrl{{display:flex;flex-wrap:wrap;gap:8px;padding:0 24px 14px;max-width:1200px;margin:0 auto;align-items:center;}}
.search-wrap{{position:relative;flex:1;min-width:180px;display:flex;align-items:center;}}
.ctrl input{{border:1.5px solid var(--bdr);border-radius:var(--r-sm);padding:8px 36px 8px 14px;font-size:13px;outline:none;width:100%;box-sizing:border-box;background:#fff;transition:border-color .15s,box-shadow .15s;}}
.ctrl input:focus{{border-color:var(--p);box-shadow:0 0 0 3px rgba(255,105,0,.1);}}
.search-clear{{position:absolute;right:10px;background:none;border:none;cursor:pointer;color:var(--lt);font-size:14px;padding:0;line-height:1;display:none;}}
.ctrl select{{border:1.5px solid var(--bdr);border-radius:var(--r-sm);padding:8px 12px;font-size:12px;background:#fff;outline:none;cursor:pointer;color:#334155;transition:border-color .15s;}}
.ctrl select:focus{{border-color:var(--p);}}
.tabs{{display:flex;}}
.tab{{padding:8px 14px;border:1.5px solid var(--bdr);font-size:12px;cursor:pointer;background:#fff;color:var(--lt);transition:all .15s;font-weight:500;}}
.tab:first-child{{border-radius:var(--r-sm) 0 0 var(--r-sm);}}
.tab:last-child{{border-radius:0 var(--r-sm) var(--r-sm) 0;border-left:none;}}
.tab.on{{background:var(--p);color:#fff;border-color:var(--p);}}
.tab:hover:not(.on){{background:var(--p-light);color:var(--p);border-color:var(--p);}}
.cnt-lbl{{font-size:12px;color:var(--lt);margin-left:auto;font-weight:500;}}

/* ── Card grid ── */
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:16px;padding:0 24px 40px;max-width:1200px;margin:0 auto;}}

/* ── Creator card ── */
.creator-card{{
  background:var(--card);border-radius:var(--r);padding:18px 18px 14px 22px;
  box-shadow:var(--sh);border:1px solid var(--bdr);
  transition:box-shadow .2s,transform .2s;
  position:relative;overflow:hidden;
}}
.creator-card::before{{
  content:'';position:absolute;left:0;top:0;bottom:0;
  width:4px;background:var(--bdr);
}}
.creator-card.tier-hi::before{{background:linear-gradient(180deg,#FF6900,#ff9500);}}
.creator-card.tier-mid::before{{background:linear-gradient(180deg,#3b82f6,#06b6d4);}}
.creator-card.tier-lo::before{{background:#e2e8f0;}}
.creator-card:hover{{box-shadow:var(--sh-lg);transform:translateY(-2px);}}

.card-header{{margin-bottom:10px;}}
.name-row{{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;}}
.creator-name{{font-size:15px;font-weight:700;color:var(--sec);}}
.creator-name:hover{{color:var(--p);text-decoration:none;}}
.creator-uid{{font-size:10px;color:var(--lt);}}
.fans-inline{{font-size:11px;color:var(--lt);margin-left:auto;}}
.cert-badge{{background:#fff8e1;color:#c05500;font-size:10px;padding:2px 8px;border-radius:10px;border:1px solid #ffe082;font-weight:600;}}
.owner-tag{{font-size:10px;color:#6366f1;background:#eef2ff;border:1px solid #c7d2fe;border-radius:10px;padding:1px 7px;font-weight:500;}}

/* Active days */
.active-days-line{{font-size:11px;color:var(--lt);display:flex;align-items:center;gap:4px;}}
.active-days-line b{{color:var(--p);font-weight:700;}}

/* Day heatmap */
.day-heatmap{{display:flex;gap:3px;margin:6px 0;}}
.day-cell{{width:24px;height:24px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;}}
.day-cell.active{{background:var(--p);color:#fff;}}
.day-cell.inactive{{background:#f1f5f9;color:#cbd5e1;}}
.day-cell.weekend-day.active{{background:#ff9500;}}
.day-cell.weekend-day.inactive{{background:#fef3e2;color:#fcd9a0;}}

/* Type tags */
.type-tags{{display:flex;flex-wrap:wrap;gap:4px;}}
.tag{{background:var(--p-light);color:var(--p);font-size:10px;padding:2px 8px;border-radius:12px;font-weight:500;}}
.tag b{{font-weight:700;}}

/* Metrics */
.metrics-row{{display:flex;border-radius:var(--r-sm);overflow:hidden;margin:8px 0;background:#f8fafc;border:1px solid var(--bdr);}}
.metric{{flex:1;padding:9px 4px;text-align:center;border-right:1px solid var(--bdr);}}
.metric:last-child{{border-right:none;}}
.metric .num{{display:block;font-size:15px;font-weight:700;color:var(--sec);line-height:1;}}
.metric .lbl{{display:block;font-size:9px;color:var(--lt);margin-top:2px;font-weight:600;text-transform:uppercase;letter-spacing:.3px;}}
.card-data-section{{margin:8px 0;}}
.card-data-label{{font-size:9px;font-weight:700;color:var(--lt);text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px;}}
.card-data-section .metrics-row{{margin:0;}}

/* Summary */
.creator-summary{{font-size:12px;line-height:1.75;color:#475569;background:linear-gradient(135deg,#f8fafc,#fff);border-left:3px solid var(--p);padding:8px 11px;border-radius:0 8px 8px 0;margin-bottom:8px;}}

/* Stocks */
.stocks-row{{font-size:12px;color:var(--lt);margin-bottom:8px;display:flex;flex-wrap:wrap;gap:4px;align-items:center;}}
.stock-tag{{background:#dbeafe;color:#1d4ed8;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:500;transition:all .15s;}}
.stock-tag:hover{{background:#1d4ed8;color:#fff;text-decoration:none;}}

/* Best post */
.best-post{{background:linear-gradient(135deg,#fafbff,#f8fafc);border-radius:8px;padding:8px 11px;font-size:12px;margin-bottom:8px;display:flex;flex-wrap:wrap;gap:5px;align-items:flex-start;border:1px solid var(--bdr);}}
.best-label{{color:var(--p);font-weight:700;white-space:nowrap;}}
.best-link{{flex:1;color:#334155;min-width:0;word-break:break-all;line-height:1.5;}}
.best-link:hover{{color:var(--p);}}
.best-metrics{{white-space:nowrap;font-size:11px;color:var(--lt);}}

/* Post list */
.posts-detail{{margin-top:8px;}}
.posts-detail summary{{font-size:12px;color:var(--p);cursor:pointer;padding:5px 0;user-select:none;outline:none;font-weight:500;}}
.posts-detail summary:hover{{opacity:.8;}}
.posts-list{{margin-top:8px;border-radius:8px;overflow:hidden;border:1px solid var(--bdr);}}
.post-row{{display:flex;flex-wrap:wrap;align-items:flex-start;gap:5px;padding:7px 10px;border-bottom:1px solid #f1f5f9;font-size:12px;background:#fff;}}
.post-row:last-child{{border-bottom:none;}}
.post-row:hover{{background:#fef9f5;}}
.post-meta{{display:flex;align-items:center;gap:4px;flex-shrink:0;}}
.post-date{{color:var(--lt);font-size:11px;white-space:nowrap;}}
.badge{{background:#f1f5f9;color:#64748b;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:500;}}
.post-link{{flex:1;color:#334155;min-width:100px;word-break:break-all;}}
.post-link:hover{{color:var(--p);}}
.post-metrics{{white-space:nowrap;font-size:11px;color:var(--lt);}}
.more-hint{{font-size:11px;color:var(--lt);text-align:center;padding:7px;background:#fafbfc;}}

/* Inactive */
.inactive-sec{{max-width:1200px;margin:0 auto 40px;padding:0 24px;}}
.inactive-sec h3{{font-size:12px;color:var(--lt);margin-bottom:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;}}
.inactive-chips{{display:flex;flex-wrap:wrap;gap:6px;}}
.inactive-chip{{background:#fff;border:1px solid var(--bdr);border-radius:8px;padding:5px 12px;font-size:12px;color:#64748b;transition:all .15s;}}
.inactive-chip:hover{{border-color:var(--p);color:var(--p);background:var(--p-light);text-decoration:none;}}

.hidden{{display:none!important;}}
.footer{{text-align:center;padding:16px;font-size:11px;color:var(--lt);border-top:1px solid var(--bdr);background:#fff;margin-top:8px;}}

/* Stats (legacy) */
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;padding:0 24px 16px;max-width:1200px;margin:0 auto;}}
.sc{{background:var(--card);border-radius:var(--r-sm);padding:14px 8px;text-align:center;box-shadow:var(--sh);}}
.sc .n{{font-size:24px;font-weight:700;color:var(--p);line-height:1;}}
.sc .l{{font-size:11px;color:var(--lt);margin-top:4px;}}

@media(max-width:600px){{
  .grid,.ctrl,.stats{{padding-left:12px;padding-right:12px;}}
  .grid{{grid-template-columns:1fr;}}
  .overview-box,.chart-sec,.top5-sec{{margin-left:12px;margin-right:12px;}}
}}
</style>
</head>
<body>

<!-- 顶部标题 -->
<div class="hdr">
  <div class="hdr-badge">WEEK {_sd.isocalendar()[1]} · {_sd.year}</div>
  <h1>🐂 富途牛牛圈 创作者运营周报</h1>
  <div class="sub">{_sd.year} 年第 {_sd.isocalendar()[1]} 周 &nbsp;·&nbsp; {_sd.month}月{_sd.day}日（周{_wk_names[_sd.weekday()]}）— {_ed.month}月{_ed.day}日（周{_wk_names[_ed.weekday()]}）</div>
  <div class="meta">数据采集于 {data["collected_at"]} &nbsp;·&nbsp; 共纳入 {data["total_creators"]} 位创作者</div>
</div>

<!-- 本周总结 -->
<div class="overview-box">
  <h2>本周总结 <span style="font-size:13px;font-weight:normal;color:#888;">（发帖量仅统计个人号，其他统计个人号+媒体号）</span></h2>
  <div class="overview-p">{weekly_overview}</div>
</div>

<!-- 点赞量 Top10 -->
{gen_top_likes_section()}

<!-- 每日分布图 -->
<div class="chart-sec" style="padding:18px 24px;">
  <h3>📅 每日发帖分布</h3>
  <div class="chart-wrap">{chart_svg}</div>
</div>

<!-- 控制栏 -->
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
    <button class="tab on" onclick="setTab('active',this)">活跃 ({len(active_creators_list)})</button>
    <button class="tab" onclick="setTab('inactive',this)">未发布 ({len(inactive_creators_list)})</button>
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
  <h3 id="inact-h3">本周未发布内容（{len(inactive_creators_list)} 人）</h3>
  <div class="inactive-chips">{gen_inactive()}</div>
</div>

<div class="footer">富途牛牛圈 创作者运营周报 &nbsp;·&nbsp; 数据来源：q.futunn.com &nbsp;·&nbsp; 每周一自动更新</div>

<script>
let curTab='active', curType='all', curOwner='all';
const cards=()=>Array.from(document.querySelectorAll('.creator-card'));

function clearSearch(){{
  document.getElementById('si').value='';
  document.getElementById('sc').style.display='none';
  filter();
}}
function filter(){{
  const q=document.getElementById('si').value.toLowerCase();
  document.getElementById('sc').style.display=q?'inline-block':'none';
  let n=0;
  cards().forEach(c=>{{
    const srch=(c.dataset.search||'').toLowerCase();
    const id=c.querySelector('.creator-uid').textContent.toLowerCase();
    const matchQ=!q||srch.includes(q)||id.includes(q);
    const matchT=curTab==='all'?true:curTab==='active'?+c.dataset.posts>0:+c.dataset.posts===0;
    const matchType=curType==='all'?true:c.dataset.accttype===curType;
    const matchOwner=curOwner==='all'?true:c.dataset.owner===curOwner;
    c.classList.toggle('hidden',!(matchQ&&matchT&&matchType&&matchOwner));
    if(matchQ&&matchT&&matchType&&matchOwner) n++;
  }});
  const showInact=curTab==='inactive'||curTab==='all';
  document.getElementById('inact').style.display=showInact?'':'none';
  let inactN=0;
  if(showInact){{
    document.querySelectorAll('.inactive-chip').forEach(chip=>{{
      const matchOwner=curOwner==='all'?true:chip.dataset.owner===curOwner;
      const matchType=curType==='all'?true:chip.dataset.accttype===curType;
      chip.style.display=(matchOwner&&matchType)?'':'none';
      if(matchOwner&&matchType) inactN++;
    }});
    document.getElementById('inact-h3').textContent='本周未发布内容（'+inactN+' 人）';
  }}
  document.getElementById('cl').textContent='显示 '+(n+inactN)+' 位';
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

function setOwner(o,el){{
  curOwner=o;
  el.closest('.tabs').querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  filter();
}}

function resort(){{
  const k=document.getElementById('ss').value;
  const g=document.getElementById('grid');
  const cs=[...g.querySelectorAll('.creator-card')];
  cs.sort((a,b)=>{{
    const keys={{posts:'posts',views:'views',likes:'likes',days:'days',fans:'fans'}};
    return +b.dataset[keys[k]]-(+a.dataset[keys[k]]);
  }});
  cs.forEach(c=>g.appendChild(c));
}}
</script>
</body>
</html>'''

week_str = data.get('week', '').replace('-', '')  # e.g. '2026-W15' -> '2026W15'
_sd_s = data.get('start_date', '').replace('-', '')[4:]  # '2026-04-06' -> '0406'
_ed_s = data.get('end_date', '').replace('-', '')[4:]    # '2026-04-12' -> '0412'
date_range = f'_{_sd_s}-{_ed_s}' if _sd_s and _ed_s else ''
out_path = os.path.join(script_dir, f'weekly_report_{week_str}{date_range}.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

# 写入报告口径统计（供 weekly_update.py 发飞书通知使用）
_stats = {
    'week': data.get('week', ''),
    'start_date': data.get('start_date', ''),
    'end_date': data.get('end_date', ''),
    'active_creators': len(active_creators_list),
    'total_creators': total,
    'w_posts': sum(len(get_own_posts(uid, v)) for uid, v in creators.items()),
    'w_views': sum(sum(p.get('views', 0) for p in get_own_posts(uid, v)) for uid, v in creators.items()),
    'w_likes': sum(sum(p.get('likes', 0) for p in get_own_posts(uid, v)) for uid, v in creators.items()),
    'w_comments': sum(sum(p.get('comments', 0) for p in get_own_posts(uid, v)) for uid, v in creators.items()),
    'ai_summary': _cached_ai_summary,
    'ai_topics': _cached_ai_topics,
}
with open(os.path.join(script_dir, 'report_stats.json'), 'w', encoding='utf-8') as f:
    json.dump(_stats, f, ensure_ascii=False)

print(f"报告已生成: {out_path}")
print(f"文件大小: {len(html)//1024} KB")

# ===== 生成 index.html（导航入口）=====
import glob as _glob, re as _re

def _report_label(fname):
    """从文件名提取显示标签，如 weekly_report_2026W16_0413-0419.html -> 2026-W16（4/13–4/19）"""
    m = _re.search(r'(\d{4})W(\d{2})_(\d{2})(\d{2})-(\d{2})(\d{2})', fname)
    if m:
        y, w, sm, sd, em, ed = m.groups()
        return f'{y}-W{w}（{int(sm)}/{int(sd)}–{int(em)}/{int(ed)}）'
    m2 = _re.search(r'(\d{4})W(\d{2})', fname)
    if m2:
        y, w = m2.groups()
        return f'{y}-W{w}'
    return fname

all_reports = sorted(
    [p for p in _glob.glob(os.path.join(script_dir, 'weekly_report_*.html'))
     if _re.search(r'\d{4}W\d{2}_\d{4}-\d{4}', os.path.basename(p))
     or _re.search(r'\d{4}W\d{2}\.html$', os.path.basename(p))],
    reverse=True
)
# 同一周有多个文件时，优先保留带日期范围的
_seen_weeks = set()
_deduped = []
for p in all_reports:
    wk = (_re.search(r'\d{4}W\d{2}', os.path.basename(p)) or type('', (), {'group': lambda s,x: ''})()).group(0)
    if wk not in _seen_weeks:
        _seen_weeks.add(wk)
        _deduped.append(p)
all_reports = _deduped
options_html = '\n'.join(
    f'<option value="{os.path.basename(p)}"{"" if i else " selected"}>{_report_label(os.path.basename(p))}</option>'
    for i, p in enumerate(all_reports)
)
latest = os.path.basename(all_reports[0]) if all_reports else ''

index_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>富途牛牛圈 创作者周报</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f7fa;}}
.nav{{position:fixed;top:0;left:0;right:0;z-index:9999;display:flex;align-items:center;gap:12px;
      padding:0 20px;height:48px;background:#fff;border-bottom:1px solid #e8ecf0;box-shadow:0 2px 8px rgba(0,0,0,.06);}}
.nav-title{{font-weight:700;color:#1a1a2e;font-size:15px;white-space:nowrap;}}
.nav select{{padding:5px 10px;border:1px solid #ddd;border-radius:6px;font-size:13px;
             background:#f8fafc;cursor:pointer;outline:none;}}
.nav select:hover{{border-color:#FF6900;}}
iframe{{position:fixed;top:48px;left:0;right:0;bottom:0;width:100%;height:calc(100vh - 48px);border:none;}}
</style>
</head>
<body>
<div class="nav">
  <span class="nav-title">🐂 富途牛牛圈 创作者周报</span>
  <select id="sel" onchange="document.getElementById('fr').src=this.value">
{options_html}
  </select>
</div>
<iframe id="fr" src="{latest}"></iframe>
</body>
</html>'''

index_path = os.path.join(script_dir, 'index.html')
with open(index_path, 'w', encoding='utf-8') as f:
    f.write(index_html)
print(f"index.html 已更新（共 {len(all_reports)} 份周报）")
