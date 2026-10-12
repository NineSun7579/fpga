"""Exclusive real-board comparison. Restore viewer only after DMA ownership ends."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

parser=argparse.ArgumentParser()
parser.add_argument('--pairs',type=int,default=2)
parser.add_argument('--warmup',type=int,default=1)
parser.add_argument('--shared',action='store_true')
parser.add_argument('--tag',default='')
args=parser.parse_args()
if args.tag and not args.tag.replace('_','').isalnum():
    raise ValueError('Invalid tag')
if not 1<=args.pairs<=10000 or not 0<=args.warmup<=100:
    raise ValueError('Invalid counts')
root=Path(__file__).resolve().parent
binary='paired_shared' if args.shared else 'paired_pointer'
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'pgrep -x make; pgrep -x cc1plus; pgrep -x ld',sudo=True)
    if out.strip():
        raise RuntimeError('Board build still active; wait for completion before a timed comparison: '+out)
    rc,out,err=board_ssh.run(client,
        'sha256sum /usr/lib/librknnrt.so /root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn '
        '/userdata/linaro/fpga-zero-copy-host/'+binary,sudo=True)
    if rc:
        raise RuntimeError(out+err)
    (root/'pointer_compare_identity.txt').write_text(out+err,encoding='utf-8')
    if 'be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9' not in out:
        raise RuntimeError('Pinned model identity mismatch')
    rc,out,err=board_ssh.run(client,'pkill -x detview-hdmiful; sleep 1; fuser /dev/pango_pci_driver',sudo=True)
    if out.strip() or 'pango_pci_driver:' in err:
        raise RuntimeError('PCIe still owned; no benchmark started: '+out+err)
    command=('/userdata/linaro/fpga-zero-copy-host/'+binary+' '
        '/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn '
        +str(args.warmup)+' '+str(args.pairs))
    label=('shared_pairs' if args.shared else 'pointer_pairs')+str(args.pairs)+('_'+args.tag if args.tag else '')
    remote='/userdata/linaro/fpga-zero-copy-host/'+label
    try:
        rc,unused,unused_err=board_ssh.run(client,command+' >'+remote+'.jsonl 2>'+remote+'.stderr',sudo=True,timeout=180)
    except Exception:
        with client.open_sftp() as sftp:
            for suffix in ('.jsonl','.stderr'):
                sftp.get(remote+suffix,str(root/(label+suffix)))
        raise
    with client.open_sftp() as sftp:
        for suffix in ('.jsonl','.stderr'):
            sftp.get(remote+suffix,str(root/(label+suffix)))
    out=(root/(label+'.jsonl')).read_text(encoding='utf-8')
    err=(root/(label+'.stderr')).read_text(encoding='utf-8')
    (root/(label+'.jsonl')).write_text(out,encoding='utf-8')
    (root/(label+'.stderr')).write_text(err,encoding='utf-8')
    print('benchmark_return_code',rc)
    if rc:
        raise RuntimeError('Benchmark failed; preserve uncertain DMA owner for explicit hardware quiescence: '+err)
    rows=[json.loads(line) for line in out.splitlines() if line.startswith('{')]
    if not rows or rows[-1].get('kind')!='pass' or rows[-1].get('pairs')!=args.pairs:
        raise RuntimeError('Missing completion receipt')
    pairs=[row for row in rows if row['kind']=='pair']
    summary={'pairs':len(pairs),'scope':('PCIe RX DMA-BUF bound input; coherent allocator backing; RKNN input cache flush disabled'
                                      if args.shared else 'borrowed PCIe RX pointer; rknn_inputs_set remains, not DMA-BUF zero-copy'),
             'input_parity':all(row['input_parity'] for row in pairs),'output_parity':all(row['output_parity'] for row in pairs)}
    for key in ('raw_dma_copy_ms','cpu_preprocess_ms','fpga_to_rx_slot_ms','cpu_rknn_ms','fpga_rknn_ms',
                'cpu_inputs_set_ms','fpga_submit_or_lease_ms','cpu_total_ms','fpga_total_ms',
                'cpu_path_process_cpu_ms','fpga_path_process_cpu_ms'):
        summary[key]=sum(row[key] for row in pairs)/len(pairs)
    summary['cpu_stage_fps']=1000/summary['cpu_total_ms']
    summary['fpga_stage_fps']=1000/summary['fpga_total_ms']
    summary['stage_fps_change_percent']=(summary['fpga_stage_fps']/summary['cpu_stage_fps']-1)*100
    (root/(label+'_summary.json')).write_text(json.dumps(summary,indent=2),encoding='utf-8')
    rc,out,err=board_ssh.run(client,'fuser /dev/pango_pci_driver',sudo=True)
    if out.strip() or 'pango_pci_driver:' in err:
        raise RuntimeError('Benchmark device descriptor not retired')
    command=('cd /userdata/detview-hdmifull; setsid nohup env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 '
        'QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl DET_BENCH=1 '
        './detview-hdmifull --model MVP_accuracy_round1 --fullscreen '
        '>/userdata/linaro/display-latency-delivery/final_acceptance.log 2>&1 </dev/null & echo $!')
    rc,out,err=board_ssh.run(client,command,sudo=True)
    if rc:
        raise RuntimeError('Viewer restart failed: '+out+err)
    summary['restored_viewer_pid']=out.strip()
    (root/(label+'_summary.json')).write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
finally:
    client.close()
