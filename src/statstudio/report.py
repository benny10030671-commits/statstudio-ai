"""Self-contained, escaped HTML reports; JSON remains the full-precision record."""
from html import escape
import json
import numpy as np


def fmt(value):
    if value is None:
        return '—'
    if isinstance(value, float):
        return format(value, '.8g')
    return str(value)


def chart_svg(chart):
    kind = chart.get('kind')
    marks = []
    xlabel, ylabel = chart.get('x_label', ''), chart.get('y_label', '')
    if kind == 'scatter':
        pairs = [(float(x), float(y)) for x, y in zip(chart['x'], chart['y']) if x is not None and y is not None]
        if not pairs:
            return ''
        xx, yy = np.array(pairs).T
        xmin, xmax, ymin, ymax = float(xx.min()), float(xx.max()), float(yy.min()), float(yy.max())
        for x, y in pairs[:2000]:
            px = 55 + (x - xmin) / (xmax - xmin or 1) * 510
            py = 275 - (y - ymin) / (ymax - ymin or 1) * 245
            marks.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3" fill="#087f8c" opacity=".7"/>')
        marks.append(f'<text x="55" y="293" font-size="11">{escape(fmt(xmin))}</text><text x="565" y="293" text-anchor="end" font-size="11">{escape(fmt(xmax))}</text>')
    elif kind in ('histogram', 'bar'):
        if kind == 'histogram':
            values = [x for x in chart.get('values', []) if x is not None]
            if not values:
                return ''
            counts, edges = np.histogram(values, bins=min(50, max(1, int(chart.get('bins', 10)))))
            labels = [f'{x:.3g}' for x in edges[:-1]]
            heights = counts.tolist()
        else:
            labels, heights = chart.get('labels', [])[:40], chart.get('values', [])[:40]
        maximum = max(heights, default=0) or 1
        for i, (label, height) in enumerate(zip(labels, heights)):
            width = 510 / max(1, len(heights))
            x, h = 55 + i * width, max(0, float(height)) / maximum * 245
            marks.append(f'<rect x="{x:.2f}" y="{275-h:.2f}" width="{max(1,width-2):.2f}" height="{h:.2f}" fill="#087f8c"><title>{escape(str(label))}: {escape(fmt(height))}</title></rect>')
            if len(labels) <= 12:
                marks.append(f'<text x="{x+width/2:.2f}" y="293" text-anchor="middle" font-size="10">{escape(str(label)[:14])}</text>')
        xmin, xmax, ymin, ymax = '', '', 0, maximum
    else:
        return ''
    title = escape(chart.get('title', ''))
    return f'<figure><figcaption>{title}</figcaption><svg viewBox="0 0 600 335" role="img" aria-label="{title}"><path d="M55 25V275H570" fill="none" stroke="#9aa"/><text x="50" y="24" text-anchor="end" font-size="11">{escape(fmt(ymax))}</text><text x="50" y="275" text-anchor="end" font-size="11">{escape(fmt(ymin))}</text>{"".join(marks)}<text x="310" y="322" text-anchor="middle" font-size="12">{escape(xlabel)}</text><text x="20" y="165" transform="rotate(-90 20 165)" text-anchor="middle" font-size="12">{escape(ylabel)}</text></svg></figure>'


def report_html(result):
    sections = []
    for table in result.get('tables', []):
        head = ''.join(f'<th>{escape(str(x))}</th>' for x in table['columns'])
        rows = ''.join('<tr>' + ''.join(f'<td>{escape(fmt(x))}</td>' for x in row) + '</tr>' for row in table['rows'])
        sections.append(f'<section><h2>{escape(table["title"])}</h2><div class="table"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div></section>')
    warnings = ''.join(f'<li>{escape(str(x))}</li>' for x in result.get('warnings', []))
    charts = ''.join(chart_svg(c) for c in result.get('charts', []))
    audit = json.dumps({k: result[k] for k in ('id', 'method', 'created_at', 'dataset', 'provenance', 'details', 'compatibility')}, ensure_ascii=False, indent=2)
    title = escape(result['title'])
    return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · StatStudio AI</title>
<style>body{{font:15px/1.65 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;color:#21333c}}h1{{font-size:30px}}h2{{font-size:18px;margin-top:30px}}.eyebrow{{color:#087f8c;letter-spacing:.12em}}.note{{background:#fff6db;padding:14px;border-radius:8px}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%}}th,td{{padding:9px 12px;border-bottom:1px solid #dde5e7;text-align:right;white-space:nowrap}}th:first-child,td:first-child{{text-align:left}}th{{background:#eef5f6}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f3f6f7;padding:20px}}figure{{max-width:640px}}figcaption{{font-weight:600}}@media print{{body{{margin:0;max-width:none}}section,figure{{break-inside:avoid}}}}</style>
<p class="eyebrow">STATSTUDIO AI / INDEPENDENT STATISTICS</p><h1>{title}</h1><p>{escape(result['dataset']['name'])} · {escape(result['created_at'])}</p>
<p class="note">{escape(result['compatibility']['description'])}</p>{''.join(sections)}{charts}<h2>分析注意事項</h2><ul>{warnings}</ul><p>HTML 顯示 8 位有效數字；完整浮點值、實際選項及套件版本請查看 JSON。圖表最多繪製 2,000 點或 40 類別，統計表使用完整有效樣本。版面為本工具設計，未聲稱與 SPSS Viewer 一致。</p><h2>重現紀錄</h2><pre>{escape(audit)}</pre></html>'''

