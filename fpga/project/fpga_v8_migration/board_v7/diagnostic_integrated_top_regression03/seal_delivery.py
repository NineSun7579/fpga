"""Independent source/trace/binding audit and Chinese evidence report."""
from pathlib import Path
import json,re,gzip,hashlib,importlib.util
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('reg03',P/'run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def save(n,v):m.save(n,v)
def main():
    # Recover audit-only after an old in-memory runner's strict observation-file
    # check; never rerun compilation/simulation, and never rewrite frozen_before.
    if not (P/'results.json').exists():m.audit()
    result=json.loads((P/'results.json').read_text(encoding='utf8'));assert result.get('functional_pass',result['pass'])
    contract=json.loads((P/'replacement_contract.json').read_text(encoding='utf8'))
    for v in ['golden','candidate']:
        for row in contract[v]:
            assert m.sha(row['source'])==row['sha256']
            assert m.sha(row['golden_source'])==row['golden_sha256']
    # Exactly the old explicit primitive expressions/attributes survive the transplant.
    a=(P/'golden/rtl/v7_sfd_candidate.v').read_bytes();b=(P/'candidate/rtl/v7_sfd_candidate.v').read_bytes()
    attrs=lambda x:re.findall(rb'\(\*.*?\*\)',x,re.S)
    prim=lambda x:re.findall(rb'GTP_DFF_(?:CE|PE)\b[^;]+;',x)
    assert attrs(a)==attrs(b) and prim(a)==prim(b)
    c=(m.C/'candidate_v7_sfd_candidate.v').read_bytes()
    norm=m.normalized
    ca=norm(c);cb=norm(b)
    counter=lambda x:x[x.index(b'module '):x.index(b'endmodule')+len(b'endmodule')]
    assert counter(cb)==counter(ca).replace(b'candidate_sfd_counter',b'v7_sfd_counter')
    gap=lambda x:x[x.index(b'module v7_camera_gap_boolean'):].rstrip()
    assert gap(cb)==gap(ca)
    ga=norm(a);start=ga.index(b'module v7_sfd_counter');end=ga.index(b'endmodule')+len(b'endmodule')
    expected=ga[:start]+counter(ca).replace(b'candidate_sfd_counter',b'v7_sfd_counter')+ga[end:]
    expected=m.replace(expected,b"    v7_sfd_counter #(.W(16)) cg(cam_clk,rst_c,edge_vs | href,1'b0,\n        count_on & seen_href & !href & !(&gap_q),gap_q,);",b"    v7_camera_gap_boolean cg(cam_clk,rst_c,capture_vsync,vs_q,href,\n        count_on & seen_href & !href & !(&gap_q),gap_q);")
    expected+=ca[ca.index(b'\n// Clear priority'):]
    assert cb==expected, 'unrequested diagnostic source change'
    for v in ['golden','candidate']:
        for name in ['scenario.vh','compare_monitor.vh','integrated_monitor.vh']:
            assert (P/v/name).read_bytes()==(m.R/'integrated'/name).read_bytes()
    # Verify CDC body exactly equals isolated Boolean candidate, modulo actual module name.
    actual=norm((P/'candidate/rtl/ov5640_cdc_tc04.v').read_bytes())
    isolated=norm((m.C/'candidate_ov5640_cdc_tc04.v').read_bytes()).replace(b'module candidate_cdc',b'module ov5640_cdc_tc04')
    assert actual==isolated
    old=json.loads((m.R/'results.json').read_text())
    audit={'compile_files_each':243,'unchanged_compile_files':241,'primitive_attributes_byte_equal':True,'primitive_instantiation_bytes_equal':True,'counter_equals_isolated_candidate_actual_name':True,'gap_equals_isolated_candidate':True,'all_other_diagnostic_bytes_equal':True,'original_scenario_monitors_byte_equal':True,'CDC_equals_isolated_candidate_actual_name':True,'traces':{}}
    for name in ['comparison.trace','integrated.trace','boolean.trace']:
        for v in ['golden','candidate']:
            f=P/v/(name+'.gz');h=hashlib.sha256();records=0;size=0
            with gzip.open(f,'rb') as src:
                for line in src:h.update(line);records+=1;size+=len(line)
            assert h.hexdigest()==result[name][v+'_sha256']
            assert records==result[name]['records'] and size==result[name]['bytes']
            assert line.startswith(b'SAMPLES ')
            if v=='golden':samples=line.decode().strip()
            else:assert samples==line.decode().strip()
        if name!='boolean.trace':assert result[name]['golden_sha256']==old[name]['sha256'],('golden differs from actual regression02',name)
        audit['traces'][name]=dict(records=result[name]['records'],bytes=result[name]['bytes'],sha256=result[name]['golden_sha256'],samples=samples,exact_regression02_trace=name!='boolean.trace')
    fields=json.loads((P/'trace_fields.json').read_text());extra=json.loads((P/'boolean_trace_fields.json').read_text())
    audit['original_signal_expressions']=sum(map(len,fields.values()));audit['extra_signal_expressions']=sum(map(len,extra.values()))
    assert audit['original_signal_expressions']==976
    warnings={}
    for v in ['golden','candidate']:
        D=P/v;t=(D/'simulation.log').read_text(errors='replace')
        assert 'TOP_FOUR_RESET_PASS checks=14668' in t
        assert 'Errors: 0' in (D/'compile.log').read_text(errors='replace')
        assert 'v7_camera_gap_boolean' in (P/'candidate/compile.log').read_text(errors='replace')
        warnings[v]=[l for l in t.splitlines() if '** Warning' in l]
    save('warnings.json',warnings)
    try:protected_count=m.freeze_check();freeze_pass=True
    except AssertionError:freeze_pass=False
    freeze=json.loads((P/'freeze_audit.json').read_text(encoding='utf8'))
    protected_count=freeze['protected_count']-len(freeze['forbidden_changes'])
    audit['protected_files_unchanged']=protected_count;audit['freeze_pass']=freeze_pass;audit['external_input_drift']=freeze['forbidden_changes']
    # Compiled closure is independently strict, including every actual RTL/IP model.
    assert all(m.sha(row['golden_source'])==row['golden_sha256'] for row in contract['golden'])
    audit['compiled_243_source_closure_unchanged']=True
    result['freeze_pass']=freeze_pass;result['pass']=result.get('functional_pass',True) and freeze_pass;save('results.json',result)
    # Two actual RTL replacement files for a future separately authorized build03.
    src=P/'src';src.mkdir(exist_ok=True)
    for name in ['v7_sfd_candidate.v','ov5640_cdc_tc04.v']:(src/name).write_bytes((P/'candidate/rtl'/name).read_bytes())
    save('src/sourcehash.json',{str(f.relative_to(P)):m.sha(f) for f in src.glob('*.v')})
    save('audit.json',audit)
    rows='\n'.join(f"| {n} | {r['records']} | {r['bytes']} | `{r['sha256']}` |" for n,r in audit['traces'].items())
    xr='\n'.join(f"- {n}：黄金/候选 X/Z 十六进制字符数 {result[n]['golden_XZ_digits']}/{result[n]['candidate_XZ_digits']}。" for n in audit['traces'])
    freeze_text='冻结通过。' if freeze_pass else '保护输入冻结 **FAIL**。以下非状态文件在本回归期间发生外部变化，原始 frozen_before 保留，未重置黄金、未忽略变化：\n\n'+'\n'.join('- `'+str(Path(x['path']).relative_to(P.parent)).replace('\\','/')+'`：`'+x['before']+'` → `'+x['after']+'`。' for x in freeze['forbidden_changes'])
    overall='功能回归 PASS；整体冻结门禁 FAIL' if not freeze_pass else 'PASS'
    report=f'''# camera boolean 候选真实整合回归03

结论：**{overall}**。黄金严格来自 regression02 的实际 integrated 源闭包；黄金与布尔候选均用 ModelSim SE-64 10.6e、真实原 FIFO/IP 模型完成原套件及四相机 reset 扩展，每侧 **14668** 检查。所有 trace 逐记录四态一致。没有 PDS、远程或设备操作，不主张时序改善。

## 源闭包与实例绑定

每侧实际编译 **243** RTL/IP/model 文件，**241** 文件字节相同；仅 `rtl/v7_sfd_candidate.v` 与 `rtl/ov5640_cdc_tc04.v` 改变。黄金沿用 regression02 原 camera/control/lease 三项优化及当前 explicit primitive。counter 的 actual module 名保持 `v7_sfd_counter`，其他八个 counter 仍按原 W 参数使用通用实现，q 的最终 clear bitmask 来自 isolated 候选，组合 next_q 的原语义不变。四路 cg 从 `v7_sfd_counter #(.W(16))` 精确改绑 `v7_camera_gap_boolean`；gap 模块字节和候选相同，不改其它参数。

四路实际 CDC 绑定 `ov5640_cdc_tc04`；其内容与 isolated candidate 仅 module 名不同。所有计数/快照/FIFO 接线保持原语义。真实 compile.log 和 hierarchy.txt、results.json 证明诊断 source、专用 gap、CDC、FIFO/IP 被编译和加载。诊断 primitive 实例保持 **28 CE / 32 PE**；属性和 primitive 实例文本独立按字节验证相同。没有接入 map02。

## 真实 trace 审计

保留原 **976** 信号表达式、36组 integrated trace 和原 comparison monitor；额外 **{audit['extra_signal_expressions']}** 表达式、12组 boolean trace 观察四路 gap q、八个通用 counter q/next_q/prefix、诊断计数/mailbox/host_bank/reset握手及 CDC count/drop/prefix/snapshot/FIFO状态。专用 gap 内部 prefix 不要求与原层级同名，q 必须一致。

所有 host/camera 正沿、camera 负沿和 control 正沿均采样，post-NBA偏移2/3/4/5ps。原 trace 沿用20ns复位后起点；新 boolean trace 从第一时钟沿开始，包含初始未知、seed和reset行为，没有新增 X 屏蔽或延迟补偿。以四态 !== 检测记录变化，连续相同值无损省略，每次采样仍计数；两侧逐记录及最终 SAMPLES 比较相同。

| Trace | 记录数 | 解压字节 | SHA256 |
|---|---:|---:|---|
{rows}

两项原 trace 的黄金 SHA256 还与 regression02 已封存结果完全一致，防止重新生成的黄金漂移。boolean trace 从首个边沿开始比较。X/Z 原值保留；下列为实际记录数据十六进制字符数，不等同于独立未知信号数量：

{xr}

新增 boolean trace 的12个X/Z字符均位于首次host采样（原始日志timestamp=5000000）：四路diag组各1个、四路CDC组各2个。initial_unknown_locations.json 保留记录号、组名及原始payload；所有未知值在两侧完全相同，未屏蔽。原 integrated trace 的未知值也与 regression02 的原封存哈希一致。

警告黄金/候选 **{result['golden']['warnings']}/{result['candidate']['warnings']}**；原文存 warnings.json 和真实日志，不能作为物理验收。每侧原计数 M01_reads=1234、M01_writes=214、legacy_reads=17；四路640x480帧检查及全部reset标记保存在 results.json。原边沿 counts 和额外 SAMPLES 均保留于 trace 尾及仿真日志。

实际 integrated 每侧 host=1158545、camera posedge=827533、camera negedge=827532、control=289637；comparison host=1158545、camera=827533、reset=18。新 boolean trace 的每侧实际总采样尾记录为 `{audit['traces']['boolean.trace']['samples']}`，两侧完全一致，含20ns前初始采样。

## 冻结与采用范围

实际编译的 **243** 个黄金源文件/IP模型及候选副本全部与开跑冻结哈希一致，源闭包无漂移；**{protected_count} / {freeze['protected_count']}** 个其它保护输入前后相同。frozen_before/after.json、freeze_audit.json、replacement_contract.json、compile_delta.json、audit.json 为依据。唯一排除的观察文件为 `source_diagnostics_timing_build_02/STATUS.md`，其前后哈希及任何漂移仍记录于 freeze_audit.json；该例外不适用于 RTL、IP/model、脚本、工程、manifest 或其它证据。没有重置 frozen_before。本子会话全部写入限定 regression03。`src/` 内两份 actual module RTL 可供未来独立 build03 使用，src/sourcehash.json 记录字节；本子会话未写活动 build02、生产 RTL 或 map02。

{freeze_text}

限制继承原整合TB：强制 AXI/control 时钟、DDR init 和 I2C completion，free_clk 停止。虽使用真实 FIFO/IP models，此套件仍不能证明完整 DMA 帧 DDR 写入、DDR校准、PCIe训练、整机吞吐或 cooperative 端到端处理。motion history 为四路8bit×19200 RTL数组，非32个已验收物理RAM primitive。不包含综合、布局布线、STA或时序 PASS。

复现：`C:/Users/NineSun/anaconda3/python.exe project/fpga_v8_migration/board_v7/diagnostic_integrated_top_regression03/run.py`，完成后运行同目录 `seal_delivery.py`。hashlog.json 封存全部交付文件（排除work、__pycache__、vsim.wlf、transcript及hashlog本身）。
'''
    (P/'REPORT_ZH.md').write_text(report,encoding='utf8')
    hashes={str(f.relative_to(P)):m.sha(f) for f in sorted(P.rglob('*')) if f.is_file() and not any(x in f.parts for x in ['work','__pycache__']) and f.name not in ['hashlog.json','vsim.wlf','transcript']}
    save('hashlog.json',hashes)
    print('INDEPENDENT_FUNCTIONAL_DELIVERY_AUDIT_PASS freeze_pass='+str(freeze_pass),json.dumps(audit,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
