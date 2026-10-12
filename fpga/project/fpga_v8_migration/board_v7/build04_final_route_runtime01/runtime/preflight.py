"""Local dependency bridge. Old controllers are never imported."""
from contract import HERE,BOARD,SOURCE,load,sha,require,verify_inputs
import json
DATA=HERE/'baseline_data'
def save(name,value):
    p=(HERE/'evidence'/name).resolve()
    require(p.is_relative_to(HERE.resolve()),'External evidence write refused')
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2)+'\n',encoding='ascii')
