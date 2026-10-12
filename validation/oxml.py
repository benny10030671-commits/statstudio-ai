"""Lossless numeric-cell extraction from our own SPSS OMS fixture outputs."""
from pathlib import Path
import xml.etree.ElementTree as ET


def local(tag):
    return tag.rsplit('}',1)[-1]


def extract(path):
    root=ET.parse(path).getroot()
    tables=[]
    for element in root.iter():
        if local(element.tag)!='pivotTable':continue
        table={'subtype':element.get('subType'),'title':element.get('text_eng',element.get('text')),'cells':[]}
        def walk(node, categories):
            kind=local(node.tag)
            if kind in ('category','group'):
                categories=categories+[node.get('text_eng',node.get('text',''))]
            if kind=='cell' and 'number' in node.attrib:
                table['cells'].append({'path':categories,'number':float(node.get('number')),'number_raw':node.get('number'),'text':node.get('text'),'format':node.get('format'),'decimals':node.get('decimals')})
            for child in node:walk(child,categories)
        walk(element,[])
        tables.append(table)
    return tables


if __name__=='__main__':
    import json,sys
    for name in sys.argv[1:]:
        path=Path(name)
        print(path.name)
        for table in extract(path):
            if table['subtype']=='Notes':continue
            print(table['subtype'],table['title'])
            for cell in table['cells'][:14]:print(json.dumps(cell,ensure_ascii=False))
