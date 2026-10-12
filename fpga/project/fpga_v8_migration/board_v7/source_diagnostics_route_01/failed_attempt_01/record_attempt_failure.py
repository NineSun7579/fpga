from prepare_route import *
def main():
    idle('failed_attempt_archive')
    out=HERE/'failed_physical_01';out.mkdir()
    for name in ['pnr_shell.log','pnr_result.json','pnr_launch.json','project.pds','flow.log','impl.tcl']:
        shutil.copyfile(HERE/name,out/name)
    shutil.copytree(HERE/'synthesize',out/'synthesize')
    shutil.copytree(HERE/'physical_constraints',out/'physical_constraints')
    save('pnr_result.json',{'exit_code':0,'actual_pnr_completed':False,'failure':'Synthesis precheck cannot resolve post-synthesis mailbox CLK pins; CommandTiming-0057 / ConstraintEditor-0046; no routed DB','timing_verified':False,'attempt_archive':str(out)})
    (HERE/'STATUS.md').write_text('# Route01 物理诊断\n\n首次 -run pnr 返回0，但综合前置约束检查失败，未进入实际PNR，未产生routed DB。完整失败记录保留 failed_physical_01；正在修正只在实际综合DB阶段加载物理对象约束的启动方式。\n\n28同步/32独立reset实际保护/拓扑审核通过；完整物理验收OPEN，未生成bit/未烧录/无remote。目标仍CAM1根因诊断。\n',encoding='utf8')
if __name__=='__main__':main()
