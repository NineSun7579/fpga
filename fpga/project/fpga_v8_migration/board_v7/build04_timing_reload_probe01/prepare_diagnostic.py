from prepare import E,BOARD,sha,save
from pathlib import Path
import shutil,pymupdf
D=BOARD/'build04_diagnostic_behavior_route01'
seal=__import__('json').loads((D/'final_result.json').read_bytes())['routed_adf']
rows=[]
for key,hkey in [('final_route','sha256'),('prr','prr_sha256')]:
 src=Path(seal[key]);assert sha(src)==seal[hkey]
 dst=E/'inputs/diagnostic_only'/src.name;dst.parent.mkdir(parents=True,exist_ok=True)
 assert not dst.exists();shutil.copy2(src,dst);assert sha(dst)==sha(src)
 rows.append(dict(source=str(src),copy=str(dst),sha256=sha(dst),bytes=dst.stat().st_size))
save('diagnostic_copy_manifest.json',dict(production_identity=False,purpose='loading semantics only; not production mapped identity',files=rows))
pdf=Path('C:/pango/PDS_2022.2-SP6.4/doc/Timing_Analyzer_User_Guide.pdf')
text='\n'.join('PAGE '+str(i+1)+'\n'+p.get_text() for i,p in enumerate(pymupdf.open(pdf)))
(E/'official_docs/Timing_Analyzer_User_Guide.txt').write_text(text,encoding='utf-8')
save('official_ta_pdf.json',dict(path=str(pdf),sha256=sha(pdf),extracted_sha256=sha(E/'official_docs/Timing_Analyzer_User_Guide.txt')))
