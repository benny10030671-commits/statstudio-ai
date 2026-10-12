"""SPSS OXML evidence, preserving precision, display strings and footnotes."""
import base64
from html import escape
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def local(tag):
    return tag.rsplit('}', 1)[-1]


def parse_output(path: Path, analysis_id: str):
    root = ET.parse(path).getroot()
    result = {'tables': [], 'charts': [], 'messages': []}
    def label(node):
        return node.get('text_eng', node.get('text', ''))
    def visit(node, command='', chart_title=''):
        kind = local(node.tag)
        if kind == 'command':
            command = node.get('command', label(node))
        if kind == 'chartTitle':
            chart_title = label(node)
        if kind == 'pivotTable':
            table_id = f'{analysis_id}:t{len(result["tables"]) + 1}'
            table = {'id': table_id, 'command': command, 'subtype': node.get('subType'),
                     'title': label(node), 'cells': [],
                     'notes': list(dict.fromkeys(label(n) for n in node.iter() if local(n.tag) == 'note'))}
            def cells(element, labels):
                tag = local(element.tag)
                if tag in ('category', 'group'):
                    labels = labels + [label(element)]
                if tag == 'cell':
                    raw = element.get('number')
                    value = float(raw) if raw is not None else None
                    table['cells'].append({'id': f'{table_id}:c{len(table["cells"]) + 1}', 'path': labels,
                                           'number': value if value is not None and math.isfinite(value) else None,
                                           'number_raw': raw, 'text': element.get('text', ''),
                                           'attributes': dict(element.attrib),
                                           'notes': [label(n) for n in element.iter() if local(n.tag) == 'note']})
                for child in element:
                    cells(child, labels)
            cells(node, [])
            result['tables'].append(table)
            if 'warning' in str(table['subtype']).lower():
                result['messages'].extend(c['text'] for c in table['cells'])
            return
        if kind == 'chart' and node.get('imageFile'):
            target = (path.parent / node.get('imageFile')).resolve()
            if not target.is_relative_to(path.parent.resolve()) or target.suffix.lower() != '.png':
                raise ValueError('Chart path escapes its analysis output directory.')
            if not target.is_file():
                raise ValueError('SPSS referenced a missing chart image.')
            result['charts'].append({'id': f'{analysis_id}:g{len(result["charts"]) + 1}',
                                     'command': command, 'title': chart_title, 'path': str(target)})
        if kind in ('warning', 'textBlock', 'text'):
            text = label(node) or ''.join(node.itertext()).strip()
            if text:
                result['messages'].append(text)
        for child in node:
            visit(child, command, chart_title)
    visit(root)
    return result


def render_report(result, interpretation=None):
    """Portable HTML, escaped text only; charts embedded rather than external URLs."""
    esc = lambda value: escape(str(value), quote=True)
    parts = ['<!doctype html><html lang="zh-Hant"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>SPSS AI 研究報告</title><style>body{max-width:1100px;margin:40px auto;padding:0 24px;font:16px/1.6 system-ui;color:#182a35}h1,h2,h3{color:#125b63}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ccd8dc;padding:6px;text-align:left;overflow-wrap:anywhere}th{background:#edf5f5}img{max-width:100%;height:auto}pre{white-space:pre-wrap}aside{padding:15px;background:#fff4d9}small{color:#51616a}a{color:#006b78}section{margin:32px 0}@media print{details{display:block}img{max-height:650px}tr{break-inside:avoid}}</style>',
             '<h1>SPSS AI 研究報告</h1>', '<p>' + esc(result['plan']['question']) + '</p>',
             '<p>執行狀態：' + ('完成' if result['status'] == 'completed' else '未完成，請檢查執行紀錄') + ' · IBM SPSS ' + esc(result.get('worker', {}).get('spss_version', 'unknown')) + '</p>',
             '<details><summary>查看分析與重現資訊</summary><small>研究計畫 ' + esc(result['plan_id']) + ' · 執行 ' + esc(result['id']) + ' · 資料 SHA-256 ' + esc(result['dataset']['sha256']) + '</small></details>']
    if interpretation:
        parts += ['<section><h2>AI 解讀</h2><p>' + esc(interpretation['summary']) + '</p>']
        for finding in interpretation['findings']:
            links = ' '.join('<a href="#' + esc(ref) + '" title="' + esc(ref) + '">[依據 ' + str(i + 1) + ']</a>' for i, ref in enumerate(finding['evidence']))
            parts.append('<p>' + esc(finding['text']) + ' ' + links + '</p>')
        parts += ['<h3>假設檢查</h3><p>' + esc(interpretation['assumptions_review']) + '</p>',
                  '<h3>限制</h3><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in interpretation['limitations']) + '</ul>',
                  '<h3>下一步</h3><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in interpretation['next_steps']) + '</ul>',
                  '<small>解讀作者：' + esc(interpretation['author']) + '。來源 ID 已核對存在；文字推論仍需審閱。</small></section>']
    else:
        parts.append('<aside>這是 SPSS 原生結果，尚未附上 AI 解讀。AI 需查看表格與圖形後另存解讀。</aside>')
    parts.append('<h2>研究設計</h2><p>' + esc(result['plan']['observation_unit']) + '；' + esc(result['plan']['sampling_and_assignment']) + '</p>')
    for analysis in result['analyses']:
        parts.append('<section><h2>' + esc(analysis['id']) + ' · ' + esc(analysis['method']) + '</h2>')
        for message in analysis.get('messages', []):
            parts.append('<aside>' + esc(message) + '</aside>')
        for table in analysis.get('tables', []):
            parts.append('<details open><summary id="' + esc(table['id']) + '"><b>' + esc(table['title']) + '</b> · ' + esc(table['id']) + '</summary><table><thead><tr><th>項目</th><th>SPSS 顯示</th><th>OMS 原始值</th></tr></thead><tbody>')
            for cell in table['cells']:
                parts.append('<tr id="' + esc(cell['id']) + '"><td>' + esc(' / '.join(cell['path'])) + '</td><td>' + esc(cell['text']) + '</td><td>' + esc(cell['number_raw'] or '') + '</td></tr>')
            parts.append('</tbody></table><small>' + '<br>'.join(esc(x) for x in table['notes']) + '</small></details>')
        for chart in analysis.get('charts', []):
            raw = base64.b64encode(Path(chart['path']).read_bytes()).decode('ascii')
            parts.append('<figure id="' + esc(chart['id']) + '"><img alt="' + esc(chart['title']) + '" src="data:image/png;base64,' + raw + '"><figcaption>' + esc(chart['id']) + ' · ' + esc(chart['title']) + '</figcaption></figure>')
        parts.append('</section>')
    parts.append('<p>圖與表來自此次 SPSS 執行；未將其他引擎輸出冒充 SPSS。完整語法與原始 .spv / .xml 另存於本機執行資料夾。</p></html>')
    return '\n'.join(parts)
