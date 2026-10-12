import xml.etree.ElementTree as ET

def flatten(rows):
    for row in rows:
        yield row
        yield from flatten(row.get('children',[]))

def extract(path):
    result={}
    if not path.exists():return result
    for event,elem in ET.iterparse(path,events=['end']):
        if elem.tag=='table':
            ident=elem.attrib.get('id','')
            if any(k in ident for k in ['clock_summary','clock_interaction','exception_report_set_max_delay','exception_report_set_false_path']):
                def row(e):return {'data':[d.text or '' for d in e.findall('data')],'children':[row(x) for x in e.findall('row')]}
                result[ident]={'headers':[x.text or '' for x in elem.findall('column_headers/data')],'rows':[row(x) for x in elem.findall('row')]}
            elem.clear()
    return result

