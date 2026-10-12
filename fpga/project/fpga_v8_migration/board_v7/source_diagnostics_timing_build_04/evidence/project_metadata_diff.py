from pathlib import Path
import re,difflib
h=Path(__file__).resolve().parent.parent
def norm(text):
    for key in ['_timespec','_gci_state','_db_output','_output']:
        while True:
            f=re.search(r'\('+key+r'(?=\s)',text)
            if not f:break
            depth=0;quoted=False
            for i in range(f.start(),len(text)):
                c=text[i]
                if c=='"':quoted=not quoted
                if not quoted:
                    if c=='(':depth+=1
                    elif c==')':
                        depth-=1
                        if depth==0:break
            text=text[:f.start()]+text[i+1:]
    return [x.strip() for x in text.splitlines() if x.strip()]
a=norm((h/'project_template.pds').read_text().replace('constraints_templates/','constraints_live/'))
b=norm((h/'project.pds').read_text())
print('\n'.join(difflib.unified_diff(a,b)))
