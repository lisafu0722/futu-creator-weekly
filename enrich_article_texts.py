"""
为原创文章抓取全文并用 Claude Haiku 生成市场内容摘要
口径：非媒体号 + author_uid == uid + feed_type_str == '文章'
结果写入每篇文章的 ai_summary 字段，保存回 week_data_enriched.json
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

import json, os, time
import anthropic
from playwright.sync_api import sync_playwright

script_dir = os.path.dirname(os.path.abspath(__file__))

MEDIA_UIDS = {'1162342', '5977079', '33792705', '28424063', '7388642', '17567706', '26294087'}

EXTRACT_JS = '''() => {
    const state = window.__INITIAL_STATE__;
    if (!state || !state.detail) return null;
    function unwrap(obj) {
        if (obj && typeof obj === 'object' && obj.__v_isRef)
            return unwrap(obj._rawValue !== undefined ? obj._rawValue : obj._value);
        return obj;
    }
    const rawMod = unwrap(state.detail.moduleData);
    if (!Array.isArray(rawMod)) return null;
    let parts = [];
    function walkNode(node, depth) {
        if (!node || typeof node !== 'object' || depth > 20) return;
        if (node.type === 0 && node.text) { parts.push(node.text); return; }
        if (node.type === 3 && node.stock && node.stock.stock_name) {
            parts.push('$' + node.stock.stock_name + '$');
            return;
        }
        const children = node.children || node.data || [];
        if (Array.isArray(children)) children.forEach(c => walkNode(c, depth + 1));
    }
    for (const m of rawMod) {
        const mod = unwrap(m);
        if (!mod) continue;
        if (mod.type === 0 && Array.isArray(mod.data))
            mod.data.forEach(n => walkNode(n, 0));
    }
    return parts.join('').trim() || null;
}'''

SUMMARY_PROMPT = (
    '以下是一篇港股/美股分析文章正文。'
    '只输出一句话（30-60字），提炼文章核心市场观点：涉及哪些指数/个股/板块、方向如何。'
    '纯文本，无markdown，无换行，直接输出结论。\n\n'
)


def fetch_full_text(page, feed_id):
    url = f'https://q.futunn.com/feed/{feed_id}'
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=20000)
        page.wait_for_timeout(1500)
        text = page.evaluate(EXTRACT_JS)
        return text or ''
    except Exception as e:
        print(f'    [fetch error] {feed_id}: {e}')
        return ''


def generate_ai_summary(client, full_text):
    if not full_text or len(full_text) < 50:
        return ''
    try:
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=100,
            messages=[{
                'role': 'user',
                'content': SUMMARY_PROMPT + full_text[:2500]
            }]
        )
        raw = msg.content[0].text.strip()
        # 取第一句，去掉markdown符号
        import re as _re
        raw = _re.sub(r'[#*`>]', '', raw).strip()
        first = _re.split(r'[。\n]', raw)[0].strip()
        return (first + '。') if first and not first.endswith('。') else first
    except Exception as e:
        print(f'    [api error]: {e}')
        return ''


def main(target_uids=None):
    data_file = os.path.join(script_dir, 'week_data_enriched.json')
    with open(data_file, encoding='utf-8') as f:
        data = json.load(f)

    cookies_file = os.path.join(script_dir, 'cookies_final.json')
    with open(cookies_file, encoding='utf-8') as f:
        cookies = json.load(f)

    ai_client = anthropic.Anthropic()

    # 确定要处理的 uid 列表
    if target_uids:
        uids = [str(u) for u in target_uids]
    else:
        uids = [uid for uid in data['creators'] if uid not in MEDIA_UIDS]

    # 统计待处理文章数
    total_arts = 0
    for uid in uids:
        v = data['creators'].get(uid, {})
        for p in v.get('posts', []):
            if (p.get('feed_type_str') == '文章'
                    and p.get('author_uid') == uid
                    and not p.get('ai_summary')):
                total_arts += 1
    print(f'待处理创作者: {len(uids)}，待提炼原创文章: {total_arts} 篇')

    done = 0
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        ctx = br.new_context(viewport={'width': 1280, 'height': 800})
        ctx.add_cookies(cookies)
        page = ctx.new_page()
        page.route('**/*.{png,jpg,gif,svg,woff,woff2,ttf,css}', lambda r: r.abort())

        for uid in uids:
            v = data['creators'].get(uid, {})
            orig_arts = [p for p in v.get('posts', [])
                         if p.get('feed_type_str') == '文章'
                         and p.get('author_uid') == uid
                         and not p.get('ai_summary')]
            if not orig_arts:
                continue

            nick = v.get('nick_name', uid)
            print(f'\n[{uid}] {nick} — {len(orig_arts)} 篇原创文章')

            for art in orig_arts:
                feed_id = art['feed_id']
                title = (art.get('title') or '')[:40]
                print(f'  抓取 {feed_id}《{title}》')

                full_text = fetch_full_text(page, feed_id)
                if full_text:
                    art['full_text'] = full_text[:3000]
                    summary = generate_ai_summary(ai_client, full_text)
                    art['ai_summary'] = summary
                    print(f'  ✓ 摘要: {summary[:80]}')
                else:
                    art['ai_summary'] = ''
                    print(f'  ✗ 未获取到正文')

                done += 1
                time.sleep(0.5)

            # 每个创作者处理完后增量保存
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        br.close()

    print(f'\n完成：共处理 {done} 篇文章，已保存到 {data_file}')


if __name__ == '__main__':
    import sys as _sys
    # 支持命令行传入 uid 列表：python enrich_article_texts.py 17296331 7223813
    targets = [int(x) for x in _sys.argv[1:]] if len(_sys.argv) > 1 else None
    main(target_uids=targets)
