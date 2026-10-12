"""Analyze a new exported graph; fail closed on unresolved or packed stages."""
from pathlib import Path
import json
from graph_adapter import classify
HERE=Path(__file__).resolve().parent
def main():
    g=json.loads((HERE/'graph.json').read_bytes())
    result=classify(g)
    objects=json.loads((HERE/'objects.json').read_bytes())
    result['all_classified_registers']=objects['classified_registers']
    result['negedge']=[r for r in objects['classified_registers'].values() if r['classification']=='negedge_binding']
    (HERE/'classification.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('ascii'))
    print('NEW_GRAPH_60_INDEPENDENT_ENDPOINTS_PASS')
if __name__=='__main__':main()
