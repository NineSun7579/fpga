from pathlib import Path
import json,hashlib
E=Path(__file__).resolve().parent
def load(n):return json.loads((E/n).read_bytes()) if (E/n).exists() else None
result=load('final_result.json');review=load('independent_review60.json')
assert result and review
passed=result['status']=='PASS_MAPPING_EXPORT_AUDIT60_ONLY' and review['status']=='PASS_PRODUCTION60_MAPPING_ONLY'
lines=['build04 mapping60_01 实际结果','', '状态：'+('PASS_PRODUCTION60_MAPPING_EXPORT_AUDIT_ONLY' if passed else 'FAIL_PRODUCTION60_MAPPING_ATTEMPT'),'',
       '仅这一新attempt；dev_map显式add_constraint原build04 clock与production60 LCF；remove_dups/const_prop/control_set_num均为官方选项0；无no_check，无时钟修改或新增timing exception。',
       '741源字节/186登记独立复核：'+str((load('independent_source741_registration186_review.json') or {}).get('status')),
       '60精确综合绑定：'+str((load('fresh60_binding.json') or {}).get('status')),
       '控制器结果：'+result['status'],'独立审计结果：'+review['status'],'']
receipt=load('mapping_receipt.json')
if receipt:
    lines+=['实际工具exit：'+str(receipt['exit_code']),'拒绝日志行：'+json.dumps(receipt['rejected_lines'],ensure_ascii=False),'原生dmr错误：'+json.dumps(receipt['native_errors'],ensure_ascii=False),'']
failure=load('actual_failure.json')
if failure:lines+=['实际失败（原样保留）：','```',failure['traceback'],'```','']
if review.get('traceback'):lines+=['后置审核：','```',review['traceback'],'```','']
if passed:lines+=['完整60 distinct gopQ：28同步 + 32复位；D/Q/CLK/reset/INIT/GRS/CE、相邻Q→D、精确时钟恒等路径和PCF/PAP_LOC/CDB位置均通过。','']
hashes={str(p.relative_to(E)):hashlib.sha256(p.read_bytes()).hexdigest() for p in E.rglob('*') if p.is_file() and p.suffix in {'.adf','.db','.pcf','.log'} and not p.is_relative_to(E/'isolated_mapping_work/synthesize')}
for n in ['mapping/analysis/graph.json','mapping/synthesis_export/synthesis_dump.txt','mapping/analysis/parse_objects.py','final_result.json','independent_review60.json','protection_before.json','protection_after.json','protection_after_failure.json','mapping_input_hashes.json','fresh60_binding.json','PDS_work_project_metadata_receipt.json']:
    p=E/n
    if p.exists():hashes[n]=hashlib.sha256(p.read_bytes()).hexdigest()
out=E/'final_evidence_hashes.json';assert not out.exists();out.write_text(json.dumps(hashes,indent=2)+'\n',encoding='ascii')
lines+=['图/ADF/dmr/PCF/log及关键receipt SHA256见final_evidence_hashes.json。','原始源、build03、map02和保护IP前后审核见protection_before及protection_after或protection_after_failure。','未运行PNR/bit/远程/program；后续由主审决定全时序/IO/bit。']
p=E/'BUILD04_MAPPING60_RESULT_ZH.md';assert not p.exists();p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('PASS_PRODUCTION60_MAPPING_EXPORT_AUDIT_ONLY' if passed else 'FAIL_PRODUCTION60_MAPPING_ATTEMPT')
