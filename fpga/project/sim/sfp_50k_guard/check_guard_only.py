from pathlib import Path
import subprocess,json,hashlib,re
R=Path(__file__).resolve().parent;W=R.parents[2];B=Path('C:/modeltech64_10.6e/win64');A=R.parent/'sfp_align';P=R.parent/'sfp_payload_probe'
T=W/'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
def run(args,name):
 p=subprocess.run([str(x) for x in args],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 t=p.stdout.decode(errors='replace');(R/name).write_text(t)
 if p.returncode:raise RuntimeError(name)
 return t
def main():
 tb=(P/'capture.sv').read_bytes().replace(b'sfp_video_tx tx(',b'sfp_video_tx #(.TX_GE_SKIP_ENABLE(0)) tx(').replace(b'actual.vec',b'guard_only.vec')
 (R/'capture_guard_only.sv').write_bytes(tb)
 for lib in ['guardtx','guardrx']:run([B/'vlib.exe',lib],lib+'_vlib.log')
 run([B/'vlog.exe','-sv','-work','guardtx',T/'video_async_fifo.v','candidate_sfp_video_tx.v','capture_guard_only.sv'],'guard_only_compile.log')
 run([B/'vsim.exe','-c','guardtx.capture','-do','onbreak {quit -code 1 -force};run -all;quit -code 0 -force'],'guard_only_capture.log')
 run([B/'vlog.exe','-sv','-work','guardrx',A/'hsst_sfp_stub.v',A/'results_before_fix/sfp_rx_link_before_fix.v',W/'project/source/sfp/sfp_video_rx.v',A/'tb_sfp_align.v'],'guard_only_rx_compile.log')
 t=run([B/'vsim.exe','-c','guardrx.tb_sfp_align','+VECTOR=guard_only.vec','+PIXELS=guard_only.pixels','+TRACE=guard_only.trace','-do','onbreak {quit -code 1 -force};run -all;quit -code 0 -force'],'guard_only.log')
 gold=[int(l,16) for l in (R/'input.hex').read_text().splitlines()];obs=[int(l,16) for l in (R/'guard_only.pixels').read_text().splitlines()]
 assert obs==gold and 'sof=1 ' in t and 'overflow=0' in t
 words=[tuple(int(x,16) for x in l.split()) for l in (R/'guard_only.vec').read_text().splitlines()]
 syms=[((d>>(j*8))&255,(k>>j)&1) for d,k in words for j in range(4)]
 matches=sum(syms[i:i+2]==[(0xbc,1),(0x50,0)] for i in range(len(syms)-1))
 guards=sum((d,k)==(0xffbcffbc,5) for d,k in words)
 assert matches==0 and guards==307200
 (R/'guard_only_summary.json').write_text(json.dumps(dict(exact_pixels=True,pixels=len(obs),guards=guards,bc50_matches=matches,receiver='archived pre-fix',sof=1,overflow=0),indent=2))
 print('PASS guard-only baseline old RX exact 614400; 307200 guards; zero BC(K)/50(D) matches')
if __name__=='__main__':main()
