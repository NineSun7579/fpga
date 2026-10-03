"""Read-only combinational-cone delay audit of existing PDS simulation artifacts.

This is an offline diagnostic (max rise/fall overapproximation), not PDS STA.
Only traces paths launched by a FF sharing the endpoint's exact CK net.
"""
from pathlib import Path
import re,json
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
text=(ROOT/'project_kf/generate_netlist/top_sim.v').read_bytes().decode('ascii',errors='replace')
sdf=(ROOT/'project_kf/generate_netlist/top_sta.sdf').read_bytes().decode('ascii',errors='replace')
cells={}; drivers={}; timing={}
def norm(s):return s.strip().replace('\\','').replace(' ','')
for m in re.finditer(r'\b(V_\w+)\s*/\*\s*(.*?)\s*\*/\s*(?:#\((.*?)\)\s*)?(\\\S+|\w+)\s*\((.*?)\);',text,re.S):
 typ,orig,params,name,ports=m.groups(); name=norm(name)
 pins={p:norm(n) for p,n in re.findall(r'\.(\w+)\s*\(([^()]*)\)',ports)}
 cells[name]=(typ,orig,pins)
 for p in ['Q','Z','Z5','COUT']:
  if pins.get(p):drivers[pins[p]]=(name,p)
for chunk in re.split(r'\( CELL\s*\r?\n',sdf)[1:]:
 match=re.search(r'\( INSTANCE ([^\s)]+)',chunk)
 if not match:continue
 name=norm(match[1]); ports={}; arcs={}; setups=[]
 for p,a,b in re.findall(r'\( PORT (\w+) \(([-\d.]+)\) \(([-\d.]+)\)',chunk):ports[p]=max(float(a),float(b))
 for p,q,a,b in re.findall(r'\( IOPATH (\w+) (\w+) \(([-\d.]+)\) \(([-\d.]+)\)',chunk):arcs[p,q]=max(float(a),float(b))
 setups=[float(x) for x in re.findall(r'\( SETUPHOLD \((?:pos|neg)edge D\) \(posedge CK\) \(([-\d.]+)\)',chunk)]
 timing[name]=(ports,arcs,max(setups,default=0))
results=[]
for endpoint,(typ,orig,pins) in cells.items():
 if 'ov5640_cdc/' not in orig or 'asyn_rempty/' not in orig or not typ.startswith('V_FF'):continue
 clock=pins['CK']; memo={}; active=set()
 def walk(net):
  if net in memo:return memo[net]
  if net not in drivers or net in active:return None
  name,out=drivers[net]; typ,orig,pins=cells[name]
  if name not in timing:return None
  ports,arcs,setup=timing[name]
  if typ.startswith('V_FF'):
   if pins.get('CK')!=clock:return None
   return (ports.get('CK',0)+arcs.get(('CK',out),0),[(name,'CK->'+out,orig)])
  active.add(net); choices=[]
  for (inp,output),delay in arcs.items():
   if output!=out or not pins.get(inp):continue
   prev=walk(pins[inp])
   if prev:choices.append((prev[0]+ports.get(inp,0)+delay,prev[1]+[(name,inp+'->'+out,orig)]))
  active.remove(net)
  memo[net]=max(choices,key=lambda x:x[0]) if choices else None
  return memo[net]
 result=walk(pins['D'])
 if result:
  ports,arcs,setup=timing[endpoint]
  required=result[0]+ports.get('D',0)+setup-ports.get('CK',0)
  results.append(dict(endpoint=orig,physical=endpoint,required_period_ps=required,
                      period_ps=7619.048,estimate_slack_ps=7619.048-required,
                      path=result[1]+[(endpoint,'D',orig)]))
print('parsed cells',len(cells),'SDF cells',len(timing),'endpoints',len(results))
for r in results:print(r['endpoint'],'estimated period ps',r['required_period_ps'],'slack ps',r['estimate_slack_ps'])
(HERE/'existing_sdf_cones.json').write_text(json.dumps(results,indent=2))
