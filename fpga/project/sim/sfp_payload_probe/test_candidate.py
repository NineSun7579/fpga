from pathlib import Path
import subprocess,json,re
R=Path(__file__).resolve().parent
B=Path('C:/modeltech64_10.6e/win64')
A=R.parent/'sfp_align'
def run(args,name):
 p=subprocess.run([str(x) for x in args],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 text=p.stdout.decode(errors='replace');(R/name).write_text(text)
 if p.returncode:raise RuntimeError(name)
 return text
tb=(A/'tb_sfp_align.v').read_bytes().replace(b'sfp_video_rx decoder',b'rx_symbol_candidate decoder').replace(b'.i_rxd(rxd), .i_rxk(rxk)',b'.i_rxd(dut.rxd_raw), .i_rxk(dut.rxk_raw)')
tb=tb.replace(b'$fclose(input_file);',b'$display("MALFORMED=%0d",decoder.bad); $fclose(input_file);')
(R/'tb_candidate.v').write_bytes(tb)
run([B/'vlib.exe','candidatework'],'candidate_vlib.log')
run([B/'vlog.exe','-sv','-work','candidatework',A/'hsst_sfp_stub.v',R.parents[1]/'source/sfp/sfp_rx_link.v','rx_symbol_candidate.sv','tb_candidate.v'],'candidate_compile.log')
gold=[int(l,16) for l in (R/'input.hex').read_text().splitlines()]
results=[]
for case in ['baseline','delete_BC28_before_B','delete_BC28_earlier_B','delete_BC50_matches']:
 text=run([B/'vsim.exe','-c','-voptargs=+acc','candidatework.tb_sfp_align',f'+VECTOR={case}.vec',f'+PIXELS=candidate_{case}.pixels',f'+TRACE=candidate_{case}.trace','-do','onbreak {quit -code 1 -force}; run -all; quit -code 0 -force'],f'candidate_{case}.log')
 m=re.search(r'RESULT pixels=(\d+) frame_pixels=(\d+) sof=(\d+) controls=(\d+) relocks=(\d+) overflow=(\d+)',text)
 row=dict(zip(['pixels','frame_pixels','sof','controls','relocks','overflow'],map(int,m.groups())))
 obs=[int(l,16) for l in (R/f'candidate_{case}.pixels').read_text().splitlines()]
 row.update(case=case,malformed=int(re.search(r'MALFORMED=(\d+)',text).group(1)),exact=obs==gold,first_mismatch=next((i for i,(a,b) in enumerate(zip(obs,gold)) if a!=b),None));print(json.dumps(row),flush=True);results.append(row)
 if case!='delete_BC50_matches':assert row['exact'] and row['sof']==1 and row['overflow']==0 and row['malformed']==0
 else:assert not row['exact'] and row['malformed']==1
(R/'candidate_summary.json').write_text(json.dumps(results,indent=2))
