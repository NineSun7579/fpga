"""Reviewed streaming parser, byte-identical records() function."""
import re
from pathlib import Path
from contract import require

def records(path):
    row = None
    with Path(path).open(encoding='gb18030', errors='replace') as stream:
        for line in stream:
            field = re.match(r'^\s*(Startpoint|Endpoint|Path Type|Path Class|Timing Exception)\s*:\s*(.*?)\s*$', line)
            if field:
                key, value = field.groups()
                if key == 'Startpoint':
                    require(row is None, 'Incomplete record without Slack before next Startpoint')
                    row = {'start': value.split(' (', 1)[0], 'end': None, 'kind': None,
                           'path_class': None, 'corner': None, 'exception': None, 'check': None, 'slack': None}
                elif row is not None:
                    name = {'Endpoint': 'end', 'Path Type': 'kind', 'Path Class': 'path_class', 'Timing Exception': 'exception'}[key]
                    row[name] = value.split(' (', 1)[0] if key == 'Endpoint' else value
                    if key == 'Path Type':
                        corner = re.search(r'\b(slow|fast)\s+corner\b', value, re.I)
                        row['corner'] = corner[1].capitalize() if corner else None
                    elif key == 'Path Class' and value.lower() in {'minimum pulse width', 'pulse width path', 'minimum pulse width path'}:
                        row['check'] = 'Minimum Pulse Width'
            if row is None:
                continue
            check = re.match(r'^\s*(Recovery|Removal|Setup|Hold)\s+time\b', line, re.I)
            if check:
                row['check'] = check[1].capitalize()
            elif re.match(r'^\s*(?:(?:Minimum|Min|High|Low)\s+)?Pulse\s+width\b', line, re.I):
                row['check'] = 'Minimum Pulse Width'
            slack = re.search(r'\bSlack\s*\((?:MET|VIOLATED)\)\s+(-?\d+(?:\.\d+)?)', line)
            if slack:
                row['slack'] = float(slack[1])
                require(row['start'] and row['end'] and row['corner'], 'Incomplete scored record fields')
                yield row
                row = None  # summaries following Slack cannot contaminate this record
    require(row is None, 'Report ends with an incomplete unscored record')

