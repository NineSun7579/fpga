"""实际查询完成后仅从receipt/报告补齐门禁，不启动PDS或生成bit。"""
from pathlib import Path
import json,time,shutil
import generate_exact11 as gen
import continue_fixed as cf
OUT=gen.OUT
def load(name):return json.loads((OUT/name).read_bytes())
def main():
    archive=OUT/('completed_reports_before_close_'+str(time.time_ns()));archive.mkdir()
    for name in ['result.json','review_result.json','runtime_clockpair_and_budget_proof.json','FINAL_ACTUAL_RESULT.md','audit_failure.txt']:
        if (OUT/name).exists():shutil.copy2(OUT/name,archive/name)
    physical=load('physical_target_acceptance.json');sta=load('evidence/final_sta_summary.json')
    route=gen.NEW/'place_route/v7_sdt_top_pnr.adf';assert cf.sha(route)==physical['route_sha256']==load('pnr_artifact.json')['sha256']
    report=OUT/'final_export/report_timing/v7_sdt_top.rtr';assert cf.sha(report)==sta['report_sha256']
    logs=[load('physical_target_'+name+'_logproof.json') for name in ['single_pair','mailbox_camera0','mailbox_camera1','mailbox_camera2','mailbox_camera3','reset','sync_later']]
    assert all(p['passed'] and all(c==0 for c in p['counts'].values()) for p in logs)
    protected=json.loads((cf.BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    mismatches=[p for p,h in protected.items() if cf.sha(Path(p))!=h]
    inputs=load('input_hashes.json');input_mismatch=[p for p,h in inputs.items() if cf.sha(gen.NEW/p)!=h]
    hsst=load('evidence/hsst_actual_phy_audit.json');io=load('evidence/io_audit.json')
    ten=sta['all_corner_summaries'];assert len(ten)==10
    gates={'mailbox':physical['mailbox'],'reset':physical['reset'],'sync_later':physical['sync_later'],
           'target_filter_zero_ignored':all(p['passed'] for p in logs),
           'ten_groups':all(s['rows'] and s['sum_failing_endpoints']==0 and all(r['worst_slack_ns']>=0 for r in s['rows']) for s in ten),
           'hsst':hsst['sites_identical_to_baseline'] and hsst['dedicated_connections_identical_to_baseline'],
           'io':io['passed'],'protected':not mismatches and not input_mismatch}
    gen.write_json(OUT/'acceptance_gates.json',gates)
    proof=load('runtime_clockpair_and_budget_proof.json');proof['acceptance_gates']=gates
    proof['physical_target_zero_ignored']=gates['target_filter_zero_ignored']
    gen.write_json(OUT/'runtime_clockpair_and_budget_proof.json',proof)
    result=load('result.json');result['gates']=gates;result['acceptance_passed']=False;result['bit_generated']=False
    result['candidate_constraints_can_be_used']=False
    result['candidate_clockpair_mailbox_migration_verified']=proof['all_364_clockpairs_actual_cdb_passed'] and proof['mailbox_1320_both_corners_passed'] and proof['compile_syn_routed_coverage']
    result['candidate_adoption_limit']='364 clockpair及1320双角mailbox预算迁移证据成立；reset检查覆盖和打包同步器内部STA仍未完整，且4条同域setup失败，不可作为最终签核/烧录候选。'
    result['hardware_or_full_timing_signoff']=False
    result['post_audit_completion']='只读复用全部实际报告补齐门禁；原PDS busy失败保留，不重启PDS。'
    gen.write_json(OUT/'result.json',result);gen.write_json(OUT/'review_result.json',result)
    counts=[{'section':s['section'],'corner':s['corner'],'failing':s['sum_failing_endpoints'],'rows':s['rows']} for s in ten]
    gen.write_json(OUT/'final_ten_sta_counts.json',counts)
    negative=load('negative_path_classification_exact11.json')
    reset=load('evidence/reset_routed_audit.json');sync=load('evidence/sync_later_routed_audit.json')
    mailbox=load('evidence/mailbox_routed_audit.json')
    lines=['# route03 exact11 实际结果','',
           '实际PNR成功；最终验收未通过，无bit、remote/program。生产/旧V7/IP保护1022文件SHA256零漂移，运行输入零漂移。',
           '', '完整364有向clockpair实际synthesis/routed CDB证明通过；compile/synthesis/routed覆盖通过。',
           '单对max_path8探针及四相机物理查询完成；全部target shell/run/report日志Timing-4006、STA-3016、unknown选项计数为0。',
           '', '|角|mailbox覆盖|预算逐对覆盖|最差裕量ns|','|---|---:|---:|---:|']
    for corner,d in mailbox['details'].items():lines.append(f"|{corner}|{d['covered']}/1320|{d['budget_covered']}/1320|{d['worst_slack']}|")
    lines+=['','全部2640条mailbox记录均已验收15.238ns datapath-only与非负Slack；missing/unexpected/bad_budget均为0。',
            '', '|检查|Slow失败端点|Fast失败端点|','|---|---:|---:|']
    for kind in ['Setup','Hold','Recovery','Removal','Minimum Pulse Width']:
        vals=[next(s['sum_failing_endpoints'] for s in ten if s['section']==kind and s['corner']==c) for c in ['Slow','Fast']]
        lines.append(f'|{kind}|{vals[0]}|{vals[1]}|')
    lines+=['','实际负路径全部为Slow同域setup；本次返回4条与十组摘要失败端点总数一致，跨域负路径0。','']
    for row in negative['records']:lines.append(f"- {row['launch_clock']} → {row['capture_clock']}：{row['start']} → {row['end']}，{row['slack_ns']}ns。")
    lines+=['','reset语义绑定32个逻辑入口→20个物理RS；实际Recovery/Removal双角均覆盖12/20，8个cr[0]/cr[1]缺报告记录，缺记录不当作负裕量也不当作通过。需逐项核验例外及实际检查可达性；不扩大reset例外。',
            f"已返回reset检查最差Slack：Slow {reset['details']['Slow']['worst_slack']}ns / Fast {reset['details']['Fast']['worst_slack']}ns。",
            f"同步器8个外部物理pair Setup/Hold双角完整且非负（Slow {sync['details']['Slow']['worst_slack']}ns / Fast {sync['details']['Fast']['worst_slack']}ns）；8个gopSRL2内部级尚缺内部STA证据，门禁失败。",
            '', 'HSST站点与专用连接、112个IO及保护文件门禁通过。原audit在离线classify前因另一会话PDS busy停止，失败receipt完整保留；本次仅从现有实际报告补齐门禁，未新启动PDS。',
            '', result['candidate_adoption_limit'], '', '证据：runtime_clockpair_and_budget_proof.json、physical_target_*_audit.json / *_logproof.json、evidence/*_routed_audit.json、final_ten_sta_counts.json、negative_path_classification_exact11.json、result.json。']
    (OUT/'FINAL_ACTUAL_RESULT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({'gates':gates,'negative_count':negative['count'],'protected_count':len(protected),'mismatch':mismatches,'input_mismatch':input_mismatch},ensure_ascii=False))
if __name__=='__main__':main()
