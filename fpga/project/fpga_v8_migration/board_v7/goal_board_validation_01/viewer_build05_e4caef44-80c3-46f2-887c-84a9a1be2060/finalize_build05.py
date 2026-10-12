"""Wait for the existing capture process, then finish receipts without rebuilding."""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import psutil

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
sys.path.insert(0,str(BASE.parents[2]/'tools'))
from board_host import ssh_connect,board_host
REMOTE='/userdata/linaro/fpga-goal-viewer-build05-e4caef44-80c3-46f2-887c-84a9a1be2060'
def utc(): return datetime.now(timezone.utc).isoformat()
def save(name,data): (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
waiting=[]
for process in psutil.process_iter(['pid','cmdline']):
    try:
        cmd=process.info['cmdline'] or []
        if process.pid!=os.getpid() and any(Path(arg).name=='capture_build05.py' for arg in cmd[1:]):
            waiting.append(process)
    except (psutil.Error,OSError): pass
save('finalization_wait_receipt05.json',dict(started_utc=utc(),waited_pids=[p.pid for p in waiting],
     mechanism='psutil Process.wait: native Windows process termination event; no build restart or file polling'))
for process in waiting:
    print('Waiting for existing capture PID',process.pid,flush=True)
    try: process.wait()
    except psutil.NoSuchProcess: pass
print('Existing capture process has ended; performing metadata comparison',flush=True)
failures=[]
for label,argv in [('compare_artifacts',[sys.executable,str(HERE/'compare_artifacts05.py')])]:
    started=utc()
    result=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (HERE/(label+'.stdout05.txt')).write_bytes(result.stdout)
    (HERE/(label+'.stderr05.txt')).write_bytes(result.stderr)
    save(label+'.receipt05.json',dict(argv=argv,started_utc=started,ended_utc=utc(),exit_code=result.returncode))
    print(label,result.returncode,result.stdout.decode(errors='replace')[:5000],flush=True)
    if result.returncode: failures.append(label+' failed; see raw stderr')
client=ssh_connect()
try:
    sftp=client.open_sftp()
    data=(HERE/'audit_trace05.py').read_bytes()
    with sftp.open(REMOTE+'/audit_trace05.py','wx') as f: f.write(data)
    started=utc(); command='python3 '+REMOTE+'/audit_trace05.py'
    _,out,err=client.exec_command(command,timeout=120)
    raw=out.read(); errors=err.read(); code=out.channel.recv_exit_status()
    (HERE/'audit_trace.stdout05.txt').write_bytes(raw)
    (HERE/'audit_trace.stderr05.txt').write_bytes(errors)
    receipt=dict(host=board_host(),command=command,started_utc=started,ended_utc=utc(),exit_code=code,
                 uploaded_script_sha256=hashlib.sha256(data).hexdigest())
    if code==0:
        remote=REMOTE+'/artifacts05/actual_read_inputs_final05.json'
        data=sftp.open(remote,'rb').read()
        (HERE/'actual_read_inputs_final05.json').write_bytes(data)
        receipt['download']=dict(remote=remote,local='actual_read_inputs_final05.json',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    else: failures.append('actual trace audit failed; see raw stderr')
    save('audit_trace.receipt05.json',receipt)
    print('audit_trace',code,raw.decode(errors='replace')[:5000],errors.decode(errors='replace'),flush=True)
finally: client.close()

def load(name,default=None):
    p=HERE/name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
build=load('build_result05.json',{})
ops=load('operations05.json',[])
audit=load('actual_read_inputs_final05.json',{})
comparison=load('artifact_comparison05.json',{})
upload=load('source_upload_receipt05.json',{})
cmpop=next((x for x in ops if x['label']=='elf_cmp'),{})
elf=comparison.get('elf') or {}
inputs=audit.get('files',[])
headers=[x for x in inputs if x.get('classification')=='header_input']
libraries=[x for x in inputs if x.get('classification')=='library_crt_or_linker_input']
missing=audit.get('missing_begin_hash',[])
changed=audit.get('changed_inputs',[])
qmake_deps=[x for x in inputs if x.get('realpath','').endswith(('.prf','.pri','.conf','.pc','.pro'))]
save('header_manifest05.json',headers)
save('library_linker_manifest05.json',libraries)
save('qmake_pro_dependencies05.json',qmake_deps)
makeout=(HERE/'make.stdout05.txt').read_text(errors='replace') if (HERE/'make.stdout05.txt').exists() else ''
compiles=[line for line in makeout.splitlines() if line.startswith('g++ -c ')]
links=[line for line in makeout.splitlines() if line.startswith('g++ -Wl,')]
save('actual_compiler_link_commands05.json',dict(compilation_commands=compiles,link_commands=links,
    full_build_verified=len(compiles)==17 and len(links)==1,source_files=len(upload.get('source_files',[]))))
device_paths=sorted({x['path'] for x in audit.get('device_opens',[])})
hardware_paths=[p for p in device_paths if p!='/dev/null']
source_valid=build.get('source_unchanged') is True
headers_valid=all(x.get('start_end_matched') for x in headers)
libraries_valid=all(x.get('start_end_matched') for x in libraries)
unresolved=audit.get('unresolved_trace_lines',[])
binding=bool(build.get('make_exit_code')==0 and source_valid and headers and libraries and headers_valid
             and libraries_valid and not changed and not unresolved and not audit.get('successful_chdir')
             and len(compiles)==17 and len(links)==1 and comparison.get('toolchain_start_end_matched')
             and not audit.get('viewer_or_selftest_executed') and not hardware_paths)
summary=dict(captured_utc=utc(),remote_root=REMOTE,qmake_returncode=build.get('qmake_exit_code'),
     make_returncode=build.get('make_exit_code'),cmp_returncode=cmpop.get('exit_code'),
     candidate_elf=build.get('elf'),deployed_sha256=elf.get('old_sha256'),byte_identical=elf.get('byte_identical'),
     source_unchanged=source_valid,protected_unchanged=build.get('protected_unchanged'),
     tools_unchanged=comparison.get('toolchain_start_end_matched'),source_input_count=len(upload.get('source_files',[])),
     compile_count=len(compiles),link_count=len(links),header_count=len(headers),library_linker_count=len(libraries),
     headers_start_end_matched=headers_valid,libraries_start_end_matched=libraries_valid,
     qmake_dependency_count=len(qmake_deps),missing_before_hash=[x['path'] for x in missing],
     changed_inputs=[x['path'] for x in changed],unresolved_trace_count=len(unresolved),
     device_paths=device_paths,hardware_device_paths=hardware_paths,viewer_or_selftest_executed=audit.get('viewer_or_selftest_executed'),
     current_source_header_library_build_binding_verified=binding,
     historical_receipt_reconstructed=False,failures=failures)
save('build_binding_summary05.json',summary)

objects=comparison.get('objects',[])
object_differences=[x['object'] for x in objects if not x['byte_identical']]
moc=comparison.get('moc',[])
moc_differences=[x['file'] for x in moc if not x['byte_identical']]
status='与当前部署 ELF 逐字节相同' if elf.get('byte_identical') else '与当前部署 ELF 不同' if elf else '构建/比较未完成，查看失败证据'
line='本次完整源码与实际头文件/链接输入绑定已核验。' if binding else '本次绑定仍有审计缺口，不能伪报完整 PASS。'
report=f'''# Viewer 完整隔离源码构建 05

结论：**{status}**。{line}这证明本次实际构建，不伪称恢复历史 build/deploy receipt。

唯一远端目录：`{REMOTE}`。本地目录：`{HERE.name}`。

从已校验 04 receipt 恢复 {summary['source_input_count']} 个 `.cpp/.h/.pro`，使用 `wx` 写入新目录；没有复制旧 `.o`、moc、生成 Makefile。实际保持原 flags，运行 `/usr/lib/qt5/bin/qmake -o Makefile detview.pro` 和 `/usr/bin/make -j1`。日志记录了 {len(compiles)} 条真实编译命令和 {len(links)} 条链接命令；原 SOURCES 中 selftest 翻译单元仅参与编译，未执行。

| 结果 | 实证 |
|---|---|
| qmake 退出码 | `{summary['qmake_returncode']}` |
| make 退出码 | `{summary['make_returncode']}` |
| 部署 ELF cmp 退出码 | `{summary['cmp_returncode']}` |
| 新 ELF SHA256 | `{(build.get('elf') or {}).get('sha256')}` |
| 部署 ELF SHA256 | `{elf.get('old_sha256')}` |
| 输入源码开始/结束 | `{summary['source_unchanged']}` |
| 真实 src/deploy/runscript 开始/结束 | `{summary['protected_unchanged']}` |
| qmake/moc/G++/ld/cc1plus/collect2 等工具开始/结束 | `{summary['tools_unchanged']}` |
| 实际头文件 | {len(headers)}，开始/结束匹配 `{headers_valid}` |
| 实际库/CRT/链接输入 | {len(libraries)}，开始/结束匹配 `{libraries_valid}` |

完整 stdout/stderr、UTC 起止和实际返回码：`operations05.json` 与每个 label 的 `*.stdout05.txt` / `*.stderr05.txt`。qmake/make 完整系统调用追踪：`qmake.strace05.txt` / `make.strace05.txt`，未给编译器添加 `-MD` 或改变功能 flags。

源输入摘要：`source_upload_receipt05.json`、`source_begin05.json`、`source_end05.json`。工具摘要：`tools_begin05.json`、`tools_end05.json`。系统预采样：`system_before05.json`。实际读取的头文件与库摘要：`header_manifest05.json`、`library_linker_manifest05.json`；`.pro` 与 qmake 配置/feature/pkg-config 依赖：`qmake_pro_dependencies05.json`。最终追踪重组与输入审计：`actual_read_inputs_final05.json`。

缺少开始摘要的实际输入：`{summary['missing_before_hash']}`。变化输入：`{summary['changed_inputs']}`。未解析追踪记录：{len(unresolved)}。这些限制应按原始记录解释，不能把当前完整系统预采样当作历史 sysroot 归档。

对象比较：{sum(x['byte_identical'] for x in objects)}/{len(objects)} 与旧对象字节相同；不同对象 `{object_differences}`。moc 差异 `{moc_differences}`。详细 section/函数大小比较见 `artifact_comparison05.json`；`elf_nm.stdout05.txt`、`deployed_nm.stdout05.txt` 和 `elf_size.stdout05.txt` 给出客观 nm/size 结果，不能单凭差异猜测语义原因。

本次没有部署、启动 viewer/selftest、DMA/BAR/PCI reset/BME/reboot/PDS 操作。追踪内实际 `/dev` 路径 `{device_paths}`，硬件设备路径 `{hardware_paths}`；`/dev/null` 若出现是标准工具输出丢弃路径。实际进程执行审计见 `actual_read_inputs_final05.json`，viewer/selftest 执行标志 `{summary['viewer_or_selftest_executed']}`。

源码内容始终与 04 恢复输入逐字节保持；没有修改 driving-demo/fullscreen/no-tracking/rotate-model、trafficlight-16cls/wb_v4_combo 或六路 motion/RAW 显示语义。实际 argv 沿用任务基线，不启动新 viewer 来验证运行行为。部署脚本摘要包含在 `protected_begin05.json` / `protected_end05.json`。新 ELF 保存在 `generated05__detview`，是可 review 产物，本次未替换真实部署。

采集/下载摘要：`ssh_receipt05.json`、`download_receipt05.json`、`audit_trace.receipt05.json`；比较校验：`artifact_comparison05.json`；最终结论机器回执：`build_binding_summary05.json`。收尾错误：`{failures}`。
'''
(HERE/'VIEWER_SOURCE_BINDING_BUILD05_ZH.md').write_text(report,encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
print('FINAL_REPORT',HERE/'VIEWER_SOURCE_BINDING_BUILD05_ZH.md',flush=True)
