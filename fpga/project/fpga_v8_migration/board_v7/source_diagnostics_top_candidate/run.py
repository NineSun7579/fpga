from pathlib import Path
import json, subprocess, os, re, hashlib
from sim_order import normalize
P=Path(__file__).resolve().parent
F=P.parents[1]/'whole_candidate_v7_route_01'
SIM=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
V=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
def run(exe,args,log):
    r=subprocess.run([str(SIM/exe),*map(str,args)],cwd=P,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    s=r.stdout.decode(errors='replace'); (P/log).write_text(s,encoding='utf-8')
    print(log,s[-2500:]); assert r.returncode==0,(exe,r.returncode)
    assert not re.search(r'\*\* (?:Error|Fatal)',s),log
    return s
if __name__=='__main__':
    subprocess.run([__import__('sys').executable,str(P/'generate.py')],check=True)
    if not (P/'work').exists(): run('vlib.exe',['work'],'vlib.log')
    sources=[Path(x) for x in json.loads((P/'sources.json').read_text())]
    alive=set(json.loads((F/'actual_elaboration.json').read_text())['elaborated'])|{'v7_sdt_top','v7_sdt_camera','v7_sdt_binding','v7_sdt_bus','v7_sfd_candidate','v7_sfd_counter'}
    def names(f): return set(x.decode() for x in re.findall(rb'(?m)^\s*module\s+(\w+)',f.read_bytes()))
    sources=[f for f in sources if names(f)&alive]
    reorder={'v7_sdt_top.v','fpga_v8_pcie_fifo_h2f_tc02.v','fpga_v8_pcie_dma_controller_h2f_rfg01.v','fpga_v8_pcie_dma_h2f_rfg01.v','fpga_v8_pango_pcie_top_h2f_rfg01.v'}
    sources=[normalize(f,P/'sim_views'/f.name) if f.name in reorder else f for f in sources]
    ips=[]
    for raw in re.findall(rb'\(_ip_source_item "([^"]+\.(?:v|vp))"',(F/'project.pds').read_bytes()):
        f=F/raw.decode()
        if f.suffix=='.vp' and '/ddr3/rtl/' in f.as_posix():
            f=Path(f.as_posix().replace('/ddr3/rtl/','/ddr3/sim_lib/'))
            assert f.exists(),f
        if 'example_design' in str(f) or '_tmpl.' in str(f): continue
        if f not in ips: ips.append(f)
    seen={}; unique=[]; duplicates=[]
    for f in ips:
        ns=names(f)
        if ns and ns & seen.keys():
            duplicates.append({'omitted':str(f),'modules':sorted(ns),'retained':[str(seen[n]) for n in ns if n in seen]})
            continue
        unique.append(f)
        for n in ns: seen[n]=f
    ips=unique
    (P/'ip_duplicates.json').write_text(json.dumps(duplicates,indent=2))
    # Official simulation primitives, separate library; no behavioral IP stubs.
    if not (P/'vendor').exists():
        run('vlib.exe',['vendor'],'vendor_vlib.log')
        prim=sorted(V.glob('*.v'))
        (P/'vendor.f').write_text('\n'.join('"'+str(f).replace('\\','/')+'"' for f in prim))
        run('vlog.exe',['-work','vendor','-f','vendor.f'],'vendor_compile.log')
    if not (P/'vendor_pcie.ok').exists():
        root=V/'modelsim10.2c'
        text=(root/'filelist_pciegen2_gtp.f').read_text().replace('./',root.as_posix()+'/')
        (P/'vendor_pcie.f').write_text(text)
        run('vlog.exe',['-sv','-mfcu','-work','vendor','-f','vendor_pcie.f'],'vendor_pcie_compile.log')
        (P/'vendor_pcie.ok').write_text('official filelist compile success')
    for cell in ['oserdes_e2','iserdes_e2','ddc_e2','dll_e2','hsstlp_pll','hsstlp_lane']:
        if not (P/('vendor_'+cell+'.ok')).exists():
            root=V/'modelsim10.2c'
            text=(root/('filelist_'+cell+'_gtp.f')).read_text().replace('./',root.as_posix()+'/')
            fn='vendor_'+cell+'.f';(P/fn).write_text(text)
            run('vlog.exe',['-sv','-mfcu','-work','vendor','-f',fn],'vendor_'+cell+'_compile.log')
            (P/('vendor_'+cell+'.ok')).write_text('official filelist compile success')
    (P/'compile.f').write_text('\n'.join('"'+str(f).replace('\\','/')+'"' for f in sources+ips))
    run('vlog.exe',['+incdir+'+str(F/'inputs/source/npu'),'-f','compile.f'],'compile.log')
    run('vlog.exe',[P/'tb_elab.v'],'elab_tb_compile.log')
    run('vsim.exe',['-c','-novopt','-L','vendor','work.tb_elab','-do','hierarchy.do'],'elaboration.log')
    inputs=set(sources+ips)
    inputs.add(F/'project.pds')
    for manifest in P.glob('vendor*.f'):
        inputs.add(manifest)
        for line in manifest.read_text().splitlines():
            path=Path(line.strip().strip('"'))
            if path.is_file(): inputs.add(path)
    inputs.update(Path(f) for f in json.loads((P/'sources.json').read_text()))
    (P/'compiled_hashes.json').write_text(json.dumps({str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(inputs)},indent=2))
