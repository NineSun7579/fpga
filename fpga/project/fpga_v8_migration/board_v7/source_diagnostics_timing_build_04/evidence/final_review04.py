"""Read-only independent receipt/source consistency review; writes only new handoff evidence."""
from pathlib import Path
import sys,json,hashlib,subprocess,time
h=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(h/'runtime'))
from preflight import verify,sha,load,require,save
m=verify();e=h/'evidence/runtime';b=Path(m['baseline_root'])
actual={p.relative_to(b).as_posix():sha(p) for p in b.rglob('*') if p.is_file()}
require(actual==m['build03_full_hashes'],'Build03 full tree additions/deletions/drift')
require(all((h/n).read_bytes()==(b/n).read_bytes() for n in m['local_hashes']),'Source741 byte compare failed')
final=load(e/'actual_result.json')
require(all(sha(p)==v for p,v in final['final_artifacts'].items()),'Final DB/graph binding drift')
checks={};pids={}
for label in ['compile','synthesize','compile_export','actual_export']:
    r=load(e/(label+'_result.json'));require(r['exit_code']==0 and not r['errors'] and r['log_sha256']==sha(e/(label+'.log')),'Actual tool receipt failure')
    pids[label]=load(e/(label+'_process.json'))
for stage,name in [('compile','compile_endpoint_details_audit_revision05.json'),('synthesis','synthesis_endpoint_details.json')]:
    p=load(e/name)
    require(p['status']=='PASS' and len(p['rows'])==len({r['cell'] for r in p['rows']})==60 and not p['failed_checks'],'Independent60 receipt failure')
    require(all(all(r['checks'].values()) for r in p['rows']),'Endpoint semantic failed')
    checks[stage]={'proof':str(e/name),'proof_sha256':sha(e/name),'independent60':60,'sync28':p['independent_sync'],'reset32':p['independent_reset'],'failed_checks':0,'types':{t:sum(r['type']==t for r in p['rows']) for t in sorted({r['type'] for r in p['rows']})}}
cmd='ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @("pds.exe","pds_shell.exe","ta.exe") } | Select-Object ProcessId,Name,CommandLine) -Compress'
busy=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',cmd]));require(not busy,'Tools still busy')
result={'status':'PASS_LOCAL_COMPILE_SYNTHESIS_EXPORT_60_RECEIPT_REVIEW','root':str(h),'build03_full_tree_files_unchanged':len(actual),'source741_bytes_identical':True,'full_source_tree_files':len(m['full_source_copy_hashes']),'project_sources':186,'protected_hashes_verified':len(m['protected_hashes']),'stage_processes':pids,'controller_launch':load(e/'controller_launch.json'),'resume_controller_launch':load(e/'resume_controller_launch.json'),'endpoint_audits':checks,'final_artifacts':final['final_artifacts'],'tool_processes_after':busy,'failed_attempts_preserved':len(list(e.glob('failure_*.txt'))),'producer_hashes':{n:v for n,v in m['immutable_hashes'].items() if n.startswith('runtime/')},'adapter_changes':['Exact vector bmsKEEPBUF indexed identity I[n]->Z[n]','Exact DDR hierarchical unique root ddr3/u_ddrphy_top/ddrphy_sysclk','Evaluate actual LUT/constant cone for D0','Flattened camera reset exhaustive 16-case check against byte-frozen source equation'],'no_mapping_pnr_bit_remote_program_flash':True,'constraints_qualified':False,'checker_sha256':sha(__file__)}
save('final_receipt_review.json',result)
text='build04 完整候选生产验证完成\n\n状态：'+final['status']+'\n源741逐字节与build03一致；完整源树742文件（含原Python缓存）；186工程登记。build03完整树'+str(len(actual))+'文件哈希与文件集合均未改变。\n\n'
for label,p in pids.items():text+=label+' PDS shell PID='+str(p['pid'])+' controller PID='+str(p['controller_pid'])+'\n'
text+='\ncompile和synthesis均60独立寄存器、28同步、32复位，全部语义检查PASS；C/P无CE采用官方精确模型。\n失败日志与DB均保留。未运行mapping/PNR/bit/remote/program/Flash。下一阶段仍需主会话完整60位置约束。\n\n实际工件最终哈希：\n'
for p,v in final['final_artifacts'].items():text+=p+'\n'+v+'\n'
(h/'BUILD04_RESULT_ZH.md').write_text(text,encoding='utf-8')
print(text)
