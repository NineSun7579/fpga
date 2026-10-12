"""Summarize actual receipts and hash retained evidence, without board actions."""
from pathlib import Path
import json, hashlib, datetime
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads((HERE/p).read_bytes())
def main():
    # Supplemental outer-shell receipts: times explicitly derive from retained
    # redirection/rc file metadata, not invented exact process timestamps.
    for prefix,command in [('independent_verify_delivery','python -B verify_delivery.py'),('runner','python -B run_trial.py')]:
        out=HERE/(prefix+'.stdout.txt');err=HERE/(prefix+'.stderr.txt');rc=HERE/(prefix+'.rc.txt')
        meta=dict(command=command,command_sha256=hashlib.sha256(command.encode()).hexdigest(),stdout_sha256=sha(out),stderr_sha256=sha(err),exit_code=int(rc.read_text(encoding='utf-16').strip()),stdout_created_utc=datetime.datetime.fromtimestamp(out.stat().st_ctime,datetime.timezone.utc).isoformat(),rc_file_updated_utc=datetime.datetime.fromtimestamp(rc.stat().st_mtime,datetime.timezone.utc).isoformat(),timestamp_source='Windows retained file metadata; exact board/program times are in dedicated command receipts')
        (HERE/(prefix+'.outer_receipt.json')).write_text(json.dumps(meta,indent=2),encoding='utf-8')
    result=load('result.json'); binding=load('qualifiedV7_sram.binding.json')
    receipt=Path(binding['original_receipt']);r=json.loads(receipt.read_bytes())
    assert sha(receipt)==binding['receipt_sha256']
    assert r['status']=='success' and r['mode']=='sram' and all(r['stages'].values())
    assert r['bit_sha256']==result['bit_sha256']
    assert all(sha(Path(p))==h for p,h in binding['log_sha256'].items())
    snapshots={name:load(name+'.stdout.txt') for name in ('before_reboot_fresh','before_sram','post_sram_natural_immediate','post_sram_natural_10s')}
    assert snapshots['before_reboot_fresh']['boot_id']==result['boot_before']
    assert all(snapshots[n]['boot_id']==result['boot_after'] for n in snapshots if n!='before_reboot_fresh')
    assert result['boot_before']!=result['boot_after']
    lines=[]
    for name,snapshot in snapshots.items():
        dmesg=next(item for item in snapshot['commands'] if item['argv']==['dmesg'])
        lines.append(dict(snapshot=name,boot_id=snapshot['boot_id'],pci=snapshot['pci'],roots=snapshot['pci_roots'],buses=snapshot['pci_buses'],driver_nodes=snapshot['driver_nodes'],admission_mode=snapshot['admission_mode'],kernel_pcie_lines=[line for line in dmesg['stdout'].splitlines() if any(x in line.lower() for x in ('pcie linking','pcie link fail','failed to initialize host','ltssm'))]))
    audit=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),result=result,original_program_receipt=str(receipt),vendor_stages=r['stages'],snapshot_summary=lines,ltssm_scope='Retained kernel messages report host startup LTSSM; no direct live BAR/register read was performed.',evidence={str(p.relative_to(HERE)):sha(p) for p in HERE.rglob('*') if p.is_file() and p.name not in ('audit.json','REPORT_ZH.md')},accepted=False,goal_complete=False)
    (HERE/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    report=f'''# reboot → qualifiedV7 SRAM → PCIe trial07 实际结果

已按新授权执行一次 `sudo -n reboot`，实际 boot 从 `{result['boot_before']}` 变为 `{result['boot_after']}`。

PDS 忙时没有持 global mutex。工具空闲后取得 `Global\\ov56401_PDS_single_instance`，持锁期间再次确认工具空闲，并调用原 `timing_correction_05/program_board.py`；该入口真实执行 `verify_delivery.py` 后才进入 vendor SRAM 编程。

SRAM 比特流 SHA256：`{result['bit_sha256']}`。原始 vendor receipt：`{receipt}`。全部 vendor stages 为 true（包含 program_success、final_scan_success、final_target_single、device_done），原始 cfg 日志经 actual06 的 v7_program/vendor_parser 重新解析和 hash 绑定。

直接编程后立即及约 10 秒后的自然枚举结果见 `post_sram_natural_immediate.stdout.txt` / `post_sram_natural_10s.stdout.txt`。最终 PCI 设备：`{result['final_pci']}`；驱动节点：`{result['driver_nodes']}`。

Rescan 独立结果：`{json.dumps(result['rescan'],ensure_ascii=False)}`。没有实际 root/rootport 时，没有写全局 rescan，没有假 bind/load 模块。

LTSSM 为本 boot 的内核启动日志，不能冒称编程后的实时寄存器采样。以下保留编程后快照中的实际日志：

```
{chr(10).join(lines[-1]['kernel_pcie_lines'])}
```

admission 保持 `0644`。无 Flash、GPIO144、held SBR、第二次 reboot、driver unload、viewer 启动或 admission release；未更改软件 buildhash，未交付新 candidate bit，未完成 goal。第一次只读 preflight 因过宽 viewer 名称判断退出，未执行 reboot；保留 initial_preflight.failure.json 和 stdout，后修正为实际设备 holder/映射与受管 producer 判断，不向 HDMI 进程发信号。

每次 SSH/local command 的 UTC、rc、command/stdout/stderr SHA256 见同名 receipt；完整 evidence hash 索引见 audit.json。
'''
    (HERE/'REPORT_ZH.md').write_text(report,encoding='utf-8')
    print(json.dumps(dict(boot=result['boot_after'],sram_done=r['stages']['device_done'],pci=result['final_pci'],nodes=result['driver_nodes'],rescan=result['rescan']),indent=2))
if __name__=='__main__':main()
