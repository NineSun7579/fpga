"""Offline-only dependency bridge; all writes confined to this prepare directory."""
from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parents[2]
def require(x,msg):
    if not x: raise RuntimeError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(name,obj):
    p=(HERE/'offline_bridge_evidence'/name).resolve()
    require(p.is_relative_to(HERE),'External write refused')
    require(not p.exists(),'Overwrite refused')
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2)+'\n',encoding='ascii')
