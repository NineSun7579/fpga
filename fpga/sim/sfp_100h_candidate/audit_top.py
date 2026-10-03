from pathlib import Path
import re,subprocess,json
R=Path(__file__).resolve().parent;B=Path('C:/modeltech64_10.6e/win64')
results={}
for kind in ['original','candidate']:
 p=subprocess.run([str(B/'vlog.exe'),'-sv','-work','regwork',str(R/kind/'top.v')],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 t=p.stdout.decode(errors='replace');(R/(kind+'_top_compile.log')).write_text(t)
 results[kind]=re.findall(r'\(vlog-\d+\) (.*)',t)
assert sorted(results['original'])==sorted(results['candidate']),set(results['candidate'])-set(results['original'])
(R/'top_audit.json').write_text(json.dumps(dict(baseline_errors=len(results['original']),candidate_errors=len(results['candidate']),new_errors=0),indent=2))
print(f"PASS top compile diagnostic parity: {len(results['original'])} pre-existing baseline diagnostics, zero new; full top compile NOT passed")
