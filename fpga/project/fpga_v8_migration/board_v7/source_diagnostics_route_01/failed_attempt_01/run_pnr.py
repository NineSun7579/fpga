from prepare_route import *
def main():
    idle('pnr')
    guard=json.loads((HERE/'build01_guard.json').read_bytes())
    assert all(sha(Path(p))==h for p,h in guard.items())
    assert json.loads((HERE/'protection_topology_audit.json').read_bytes())['passed']
    before={str(p.relative_to(HERE)):sha(p) for folder in ['inputs','rtl','physical_constraints'] for p in (HERE/folder).rglob('*') if p.is_file()}
    save('pnr_input_hashes.json',before)
    cmd=[str(PDS),'-project',str(HERE/'project.pds'),'-run','pnr','-work_dir',str(HERE)]
    save('pnr_launch.json',{'command':cmd,'status':'running','programming_performed':False})
    (HERE/'STATUS.md').write_text('# Route01 物理诊断\n\n真实保护属性与28同步/32独立reset拓扑审核通过；精确物理FDC已生成，原pin/IO/clock命令保留，仅迁移5条async。\n\nPNR实际运行中。完整双角STA、mailbox、reset/MPW、IO/HSST/DRM门槛待验收；未生成bit、未烧录、无remote。目标仍为CAM1根因诊断。\n',encoding='utf8')
    print('START PNR',cmd,flush=True)
    with (HERE/'pnr_shell.log').open('xb') as log:
        result=subprocess.run(cmd,cwd=HERE,stdout=log,stderr=subprocess.STDOUT)
    unchanged=all(sha(HERE/p)==h for p,h in before.items()) and all(sha(Path(p))==h for p,h in guard.items())
    raw=(HERE/'pnr_shell.log').read_bytes()
    errors=[l.decode('ascii','backslashreplace') for l in raw.splitlines() if l.startswith(b'E:')]
    missing=[l.decode('ascii','backslashreplace') for l in raw.splitlines() if b'Timing-4003' in l]
    route=HERE/'place_route/v7_sdt_top_pnr.adf'
    generated=route.is_file() and route.stat().st_size>0 and (HERE/'place_route/prr.db').is_file()
    save('pnr_result.json',{'exit_code':result.returncode,'inputs_and_build01_unchanged':unchanged,'route_generated':generated,'constraint_errors':errors,'missing_pin_messages':missing,'timing_verified':False})
    assert result.returncode==0 and unchanged and generated and not errors and not missing
    print('ROUTE DB GENERATED; physical acceptance pending',flush=True)
if __name__=='__main__':main()
