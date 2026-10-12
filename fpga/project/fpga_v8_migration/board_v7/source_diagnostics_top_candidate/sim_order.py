"""ModelSim forward-reference compatibility: move declarations, not logic.
Simulation-only views; candidate RTL and frozen inputs are untouched.
"""
import re,difflib
from pathlib import Path
def normalize(src,out):
 b=src.read_bytes()
 # Preserve the active frozen USE_OV5640 compile configuration while moving
 # declarations across its mutually exclusive HDMI source branch.
 if src.name=='v7_sdt_top.v':
  stack=[]; active=True; selected=[]; defines={b'USE_OV5640'}
  for line in b.splitlines(keepends=True):
   m=re.match(rb'\s*`(ifdef|ifndef|elsif|else|endif)\b\s*(\w*)',line)
   if m:
    op,name=m.groups()
    if op in [b'ifdef',b'ifndef']:
     cond=(name in defines) == (op==b'ifdef');stack.append([active,cond]);active=active and cond
    elif op==b'elsif':
     outer,taken=stack[-1];cond=not taken and name in defines;stack[-1][1]|=cond;active=outer and cond
    elif op==b'else':outer,taken=stack[-1];active=outer and not taken;stack[-1][1]=True
    else:active=stack.pop()[0]
   elif active:selected.append(line)
  assert not stack
  b=b''.join(selected)
  b,n=re.subn(rb'wire\s+\[7:0\]\s+prep_frame_cnt;',b'',b);assert n==1
  assert len(re.findall(rb'reg\s+\[7:0\]\s+prep_frame_cnt;',b))==1
 clean=re.sub(rb'/\*.*?\*/|//[^\r\n]*|"(?:\\.|[^"\\])*"',lambda m:b' '*len(m[0]),b,flags=re.S)
 header=clean.index(b');')+2
 depth=0; spans=[]
 tok=re.compile(rb'\b(begin|end|generate|endgenerate|function|endfunction|task|endtask|case|casex|casez|endcase|fork|join|wire|reg|localparam|integer)\b')
 skip=header
 for m in tok.finditer(clean,header):
  if m.start()<skip:continue
  word=m[0]
  if word in [b'begin',b'generate',b'function',b'task',b'case',b'casex',b'casez',b'fork']:depth+=1
  elif word in [b'end',b'endgenerate',b'endfunction',b'endtask',b'endcase',b'join']:depth-=1
  elif depth==0:
   end=clean.index(b';',m.start())+1;spans.append((m.start(),end,word));skip=end
 declarations=[]; edits=[]
 implicit={'v7_sdt_top.v':['core_clk','ddr_init_done'], 'fpga_v8_pcie_fifo_h2f_tc02.v':['fifo_rx_almost_full'], 'fpga_v8_pcie_dma_controller_h2f_rfg01.v':['total_length_cfg_done']}
 declarations += [('wire '+n+';').encode() for n in implicit.get(src.name,[])]
 for lo,hi,word in spans:
  text=b[lo:hi]; simple=clean[lo:hi]
  if word==b'wire' and b'=' in simple:
   # Initialized net declarations in these views are one net per statement.
   pos=simple.index(b'=');lhs=text[:pos].rstrip()
   assert b',' not in simple[:pos],text
   name=re.findall(rb'\b\w+\b',simple[:pos])[-1]
   declarations.append(lhs+b';');edits.append((lo,hi,b'assign '+name+b' '+text[pos:]))
  else:declarations.append(text);edits.append((lo,hi,b''))
 for lo,hi,value in reversed(edits):b=b[:lo]+value+b[hi:]
 b=b[:header]+b'\n'+b'\n'.join(declarations)+b'\n'+b[header:]
 out.parent.mkdir(exist_ok=True);out.write_bytes(b)
 (out.parent/(out.name+'.diff')).write_text(''.join(difflib.unified_diff(src.read_bytes().decode('gbk',errors='replace').splitlines(True),b.decode('gbk',errors='replace').splitlines(True))),encoding='utf-8')
 return out
