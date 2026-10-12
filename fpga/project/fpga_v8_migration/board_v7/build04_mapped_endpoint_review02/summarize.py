"""Produce readable review deliverables from actual completed audit only."""
from pathlib import Path
import json,csv,hashlib,collections
H=Path(__file__).resolve().parent
def load(n):return json.loads((H/n).read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=load('final_result.json');rr=load('rows60.json');rows=rr['rows'];pairs=load('adjacent_Q_D.json');prot=load('protection_comparison.json');prov=load('artifact_provenance.json')
fields=['camera','chain','bit','synthesis_target','cell','type','planned_site','Q','D','storage_D_function','CLK','reset','FF_RS','FF_INIT','GRS_EN','RS_MODE','CLK_POL','LRS_POL','LRS_EN','LCE_EN','QMUX_SEL','PCF','PAP_LOC','failed_checks','errors']
with (H/'rows60.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for row in rows:
  out={k:row.get(k,'') for k in fields};out.update({k:row.get('parameters',{}).get(k,'') for k in fields if k in row.get('parameters',{})})
  out['PCF']=' | '.join(x['line'] for x in row.get('actual_PCF',[]));out['PAP_LOC']=' | '.join(x['value'] for x in row.get('actual_PAP_LOC',[]))
  out['failed_checks']=' | '.join(k for k,v in row['checks'].items() if not v);out['errors']=' | '.join(row['errors']);w.writerow(out)
integrated=[x for x in rows if x.get('type')=='gopLUT6Q_Cell_139']
nonmodel=[{'target':x['synthesis_target'],'checks':[k for k,v in x['checks'].items() if not v and k!='official_gop_behavior_decoded'],'errors':x['errors']} for x in rows if x['errors'] or any(not v for k,v in x['checks'].items() if k!='official_gop_behavior_decoded')]
summary={'status':r['status'],'rows':len(rows),'distinct_cells':rr['distinct_cells'],'distinct_sites':rr['distinct_sites'],'distinct_Q_nets':rr['distinct_registered_Q_nets'],'exact_PCF_PAP_LOC_rows':sum(x['checks'].get('exact_site_binding',False) for x in rows),'parameter_match_rows':sum(all(v for k,v in x['checks'].items() if k.startswith('parameter_')) for x in rows),'clock_identity_rows':sum(x['checks'].get('exact_clock_identity',False) for x in rows),'integrated_FF0_truth_table_rows':sum(x['checks'].get('LUT_full_identity_I0',False) and x['checks'].get('D_function_original_zero',False) for x in integrated),'integrated_truth_tables_each_size':{x['synthesis_target']:len(x.get('complete_LUT_truth_table',[])) for x in integrated},'reset_cone_tables':sum(x['checks'].get('reset_function_exact_original',False) for x in rows),'reset_identity_release_Q_rows':sum(x['checks'].get('reset_identity_exact_release_Q',False) for x in rows),'D0_original_source_rows':sum(x['checks'].get('D_original_source_Q',False) for x in rows),'adjacent_pairs':pairs['count'],'adjacent_pairs_pass':pairs['passed'],'nonmodel_failures':nonmodel,'official_model_semantic_unproven_rows':sum(not x['checks'].get('official_gop_behavior_decoded',False) for x in rows),'protected_files':prot['count'],'protected_unchanged':prot['passed'],'original_FAIL_preserved':r['original_mapping60_status']=='FAIL','boundary':'Reset cone truth tables use exact retained source-register cut outputs. Those source-register transformations and storage-mux behavior are not accepted without official decoded gop semantics.'}
(H/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
text=f'''独立审查结果：{r['status']}。原 mapping60_01/final_result.json 保留 FAIL。

本地离线审查了原 mapped ADF 的既有官方 native export，未运行 PDS、PNR、bit、program 或远程操作。用原 parser 的逐字相同副本重新解析 native dump，graph SHA256 与原 graph 完全一致。

实际 60 个 retained cell / 60 个 PAP_LOC site / 60 个独立注册输出 net：28 gopQ、20 gopQ_Cell_1、12 gopLUT6Q_Cell_139。逐项数据在 rows60.json 与 rows60.csv，36 对相邻 Q-D 在 adjacent_Q_D.json。

精确 PCF+PAP_LOC 关联 {summary['exact_PCF_PAP_LOC_rows']}/60；clock identity 参数检查 {summary['clock_identity_rows']}/60；原始参数匹配 {summary['parameter_match_rows']}/60。PCF 是实际三参数 def_inst_site，没有 implementation 第四参数；mapped attributes 没有 PAP_NOPRUNE。两者如实记录，不凭空补入实现名或属性。

12 个 cr/hr/reset_pipe FF0 为一个 LUT6 加一个 FF 的结构。INIT 为 10 重复 32 次，完整 64 行 truth table 证明输出函数是 I0；I0 实际常量 0，另外 5 个 don't-care 输入穷举后全部 32 个可达组合输出均为 0。实际注册输出是 L6Q，CLK/RS 独立，后级 D 接它。通过此项的 FF0：{summary['integrated_FF0_truth_table_rows']}/12。未以 reset 根来源相同替代 LUT 函数证明。

严格 FAIL 缺口：安装的官方 gopQ/gopLUT6Q 等 .eval 文件是 PANG 二进制。已保存其 before/after hashes、官方 gopL6Q packing rule 和既有参数解码依据，但没有可读行为模型或既有解码器可证明完整 QMUX/clock/reset/CE/GRS/async 行为。官方 packing rule 仅证明 gopQ+gopLUT6 合并成 oneFF 的端口与参数映射；不能替代完整行为模型证明。60 行 official_gop_behavior_decoded 均未通过，因此不产生独立 PASS。

reset cone 的完整 16 行 truth table 比较也仅在精确 retained 原 source-register 输出边界上成立；边界上实际存在 L5Q/L6Q 和反相寄存器实现，未接受这些源寄存器变换的完整语义。具体 mapped driver records 与全部 LUT 参数/真值表已逐行留证。

非模型缺口：{json.dumps(nonmodel,ensure_ascii=False)}。

保护核验：{prot['count']} 文件 before/after SHA256 全部相同：{prot['passed']}。原 build04（含原 map/FAIL）、build03、map01、map02、保护源及计划均未修改。artifact_provenance.json 记录实际 ADF/dmr/PCF/native dump/graph/parser 和工具、parser 日志 hashes；protection_comparison.json、before_hashes.json、after_hashes.json 提供完整核验。

consumer 必要兼容改动（仅审查副本实现）：

- 从丢失的逻辑 alias 转为 fresh60 exact GTP retained ff path + planned site + actual PCF/PAP_LOC 的交叉绑定。
- host clock 使用原 u_sysclk_bufg 的精确 retained CLKOUT；ACK 输入源识别实际 L5Q。
- oneFF integrated LUT 使用实际 L6Q 作为注册输出、完整 LUT 函数作为内部 D；普通 FF 使用实际 D/Q/CLK/RS，禁止猜造 D 端口。
- 仅接受已证明的精确类型与参数；SRL、QQ、多级 pack 或未知类型必须 FAIL。取得官方 gop 行为解码依据后才可进一步作完整功能判定。

attempt_01 与 attempt_02 保留离线 consumer 修正前发现；没有重复执行 mapping/export，也没有改原结果。
'''
(H/'RESULT_ZH.md').write_text(text,encoding='utf-8')
(H/'review_output_hashes.json').write_text(json.dumps({str(p.relative_to(H)):sha(p) for p in H.rglob('*') if p.is_file() and p!=H/'review_output_hashes.json'},indent=2)+'\n',encoding='ascii')
print(json.dumps(summary,indent=2,ensure_ascii=True))
