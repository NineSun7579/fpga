# Publication qualification review — frozen run 212303

Complete-frame qualification and core capture alignment are resolved on CAM1–4. The wrapper capture predicate is fully resolved on CAM2. CAM1/3/4 have correct ABI D wiring and capture/reset structure, with an unresolved carry cone per path: `N77/gateop:COUT` (`gopA MODE=XOR`) feeds `N77_1/gateop:Y` (`gopA MODE=ARITH`). Full resource-gate acceptance stays with the parent.

Each camera passed all 4,194,304 combinations of its 19-bit `pixel_count` and start/end/active controls: `end_pending_next = !core_start && core_end && active && pixel_count==307200`. Each passed the completion-valid hold mux, result-valid pulse, and rising `axi_clk` / asynchronous zero-reset / no-CE checks for the five publication control registers. The packed SRQ register establishes `publish_pending_next=end_pending`; strobe takes old `publish_pending`. All 232 result payload bits take settled work through positive `publish_pending` CE, otherwise hold, and asynchronously reset through `N1615`. Thus a complete end at E publishes at E+2; the wrapper takes those fields at E+3.

All 266 variable record bits per camera match the frozen 320-bit ABI D-pin layout, share one positive CE per camera, and have the specified rising clock and asynchronous zero reset. CAM2's CE matches `strobe && !overflow && !overflow_reset` for all eight control combinations. CAM1/3/4 use the actual `N368` as their shared CE; ordinary LUT evaluation cannot establish its carry-dependent `gopA` Y function. No mismatch has been observed. The remaining precise obligation is to prove each `N368 = strobe && !overflow && !overflow_reset` through those two cells. Proving only `N77:Y = overflow || overflow_reset` would not settle the carry output used by capture CE. The separate arithmetic reviewer can supply that primitive interpretation without repeating the checks here.

The frozen adapter quote at lines 153–158 specifies atomic snapshot and bit packing. Existing regression receipts remain the simulation evidence; this review does not rerun simulation or claim mapped whole-design equivalence. Reserved and zero-extension bits were not new register checks; the parent's existing register-slot/ABI proof covers them. FIFO issue predicates, work arithmetic/bbox construction, and vendor compiler correctness are outside this bounded review.

The final audit verified 2,032 retained primitive quotes as literal substrings of the current dump and rechecked every recorded file hash. The frozen core and adapter hashes match the existing regression receipt. Current mapped Verilog SHA-256 is `eaf0974fc723227dfa0f71717f3f2fc1c26d50689193ee816f0aba351b07b7f0`; current ADIF SHA-256 is `8c291ebb8843cd956d84218e302f7243abae431ee56eae903ff4344177958524`. Exact source hashes and full primitive quotes are in `publication_mapped_review.json`. Only this report and that JSON are written. The executable below checkpoints its JSON after each camera.

Remaining paths (all under the named adapter): `ov5640_top/u_motion_tap`, `cam3_ov5640_top/u_motion_tap`, and `cam4_ov5640_top/u_motion_tap`. For each, the quoted first cell has `INIT=0xeeeeeeee00000000`, `MODE=XOR`, `I0=overflow`, `I1=overflow_reset`, `I5=1`, `COUT=N77_co`. The second has `INIT=0x00000000cccccccc`, `MODE=ARITH`, `I1=strobe`, `CIN=N77_co`, `Y=N368`. Its Y is the CE of every variable record bit. These are evaluator gaps rather than failing truth rows. The JSON status is `precise_gaps`; parent acceptance is not asserted.

The executable below reuses the primitive parser and bounded LUT evaluator in `four_actual_mapped_review.md`. Registered work values are explicit leaves. It tests completion qualification independently of counter arithmetic, checks every result capture D/CE/reset boundary, and checks wrapper capture qualification and ABI wiring. Arithmetic cones and upstream FIFO issue semantics belong to separate reviews.

```python
from pathlib import Path
import numpy as np
import json, hashlib, re
base = Path('log/100h_motion/four_actual_mapped_review.md').read_text()
exec(base.split('```python\n')[1].split('rows=[]')[0])
def packed(a):
    return int.from_bytes(np.packbits(np.asarray(a, dtype=np.uint8), bitorder='little').tobytes(), 'little')
def cols(a, bits):
    return [packed((a >> b) & 1) for b in range(bits)]
def support_next(net):
    result=set();seen=set()
    def inputs(x,p):
        t,bits=table(x,p)
        return [x['ports'].get('I'+str(b),'') for b in range(bits) if any(((t>>i)&1)!=((t>>(i^(1<<b)))&1) for i in range(1<<bits))]
    def trace(n):
        if n in seen:return
        seen.add(n)
        if n not in drivers:result.add(n);return
        x,p=drivers[n]
        if p in ('Q','L6Q','L5Q','L6QQ'):result.add(n);return
        for v in inputs(x,p):trace(v)
    x,p=drivers[net]
    for v in inputs(x,p):trace(v)
    return sorted(result)
evidence = {}
def keep(names):
    for name in names:
        x=instances[name]
        evidence[name]={'file':'mapped_dump.v','sha256':hashlib.sha256(raw).hexdigest(),'quote':x['quote']}
def test(leaves, n, net, expected, registered=False):
    ev, mask, used=evaluator(leaves,n)
    try:
        actual=next_data(net,ev,mask) if registered else ev(net)
        result={'pass':actual==expected}
        if actual!=expected:
            delta=actual^expected
            result['first_mismatch_row']=(delta & -delta).bit_length()-1
    except ValueError as err:
        result={'pass':False,'gap':str(err)}
    keep(used)
    if registered:keep([drivers[net][0]['instance']])
    return result
rows=[]
for camera,D in enumerate(DS,1):
    A=D.rsplit('/u_detector',1)[0]
    reset=drivers[D+'/end_pending'][0]['ports']['RS']
    row={'camera':camera,'detector':D,'checks':{},'gaps':[]}
    row['end_predicate_support']=support_next(D+'/end_pending')
    row['checks']['end_predicate_only_22_source_leaves']={'pass':set(row['end_predicate_support'])=={A+'/core_start',A+'/core_end',D+'/active',*[D+f'/pixel_count[{b}]' for b in range(19)]}}
    # Exhaust all 19 count bits for all frame_start/end/active controls.
    # Other sample-control leaves are arbitrary zero: dependence on any is a gap.
    counts=np.arange(1<<19,dtype=np.uint32); n=len(counts); mask=(1<<n)-1
    leaves={D+f'/pixel_count[{b}]':c for b,c in enumerate(cols(counts,19))}
    leaves.update({A+'/core_valid':0})
    leaves.update({D+f'/{axis}[{b}]':0 for axis in ('x','y') for b in range(2)})
    leaves.update({D+f'/sample_address[{b}]':0 for b in range(15)})
    complete=1<<307200
    ends=[]
    for control in range(8):
        fs,fe,active=[bool(control & (1<<b)) for b in range(3)]
        ll=dict(leaves);ll.update({A+'/core_start':mask if fs else 0,A+'/core_end':mask if fe else 0,D+'/active':mask if active else 0})
        ends.append(test(ll,n,D+'/end_pending',complete if not fs and fe and active else 0,True))
    row['checks']['complete_frame_end_4194304_rows']={'pass':all(x['pass'] for x in ends),'controls':ends,'expected':'!core_start && core_end && active && pixel_count==307200'}
    # Repeat with sample-related registered leaves one to detect accidental support.
    for k in list(leaves):
        if '/pixel_count[' not in k:leaves[k]=mask
    leaves.update({A+'/core_start':0,A+'/core_end':mask,D+'/active':mask})
    row['checks']['end_sample_control_independence_high']=test(leaves,n,D+'/end_pending',complete,True)
    # Completion-valid hold mux and result-valid pulse: independent truth domains.
    vv=np.arange(16,dtype=np.uint32);cc=cols(vv,4)
    ll={D+'/N9088':cc[0],D+'/publish_comparison_valid':cc[1],D+'/publish_pending':cc[2],D+'/reference_valid':cc[3]}
    row['checks']['comparison_valid_capture']=test(ll,16,D+'/publish_comparison_valid',packed(np.where(vv&1,(vv>>3)&1,(vv>>1)&1)),True)
    row['checks']['result_valid_pulse']=test(ll,16,A+'/comparison_valid',packed(((vv>>1)&1)&((vv>>2)&1)),True)
    publication=[D+'/end_pending',D+'/publish_pending',D+'/publish_comparison_valid',A+'/comparison_valid',A+'/strobe']
    row['publication_registers']={}
    for net in publication:
        chk=reg_checks(net,reset);x,p=drivers[net];keep([x['instance']])
        row['publication_registers'][net]=chk
    row['checks']['publication_clock_reset_no_ce']={'pass':all(all(c[k] for k in ('clock','rising','async_zero','reset_net','ce','latch_disabled')) and c['reset_polarity']=='FALSE' for c in row['publication_registers'].values())}
    x,p=drivers[D+'/publish_pending'];y,yp=drivers[D+'/end_pending'];z,zp=drivers[A+'/strobe']
    row['checks']['end_publish_strobe_edges']={'pass':x is y and p=='L6QQ' and yp=='L6Q' and x['parameters'].get('FFAPPMUX_SEL')=='SRQ' and z['ports'].get('D')==D+'/publish_pending'}
    pairs=[(A+f'/bitmap_word[{b}]',D+f'/bitmap_work[{b}]') for b in range(192)]
    pairs += [(A+f'/block_word[{b}]',D+f'/blocks_work[{b}]') for b in range(8)]
    pairs += [(A+f'/samples[{b}]',D+f'/samples_work[{b}]') for b in range(15)]
    pairs += [(A+'/bbox_valid',D+'/bbox_work_valid')]
    pairs += [(A+f'/{edge}{axis}_word[{b}]',D+f'/{edge}_{axis}_work[{b}]') for edge in ('min','max') for axis in ('x','y') for b in range(4)]
    capture=[]
    for net,src in pairs:
        if net not in drivers:
            capture.append({'net':net,'pass':False,'gap':'missing driver'});continue
        x,p=drivers[net];chk=reg_checks(net,reset,D+'/publish_pending');keep([x['instance']])
        ok=p=='Q' and x['ports'].get('D')==src and x['parameters'].get('LCE_POL')=='FALSE' and chk['reset_polarity']=='FALSE' and all(chk[k] for k in ('clock','rising','async_zero','reset_net','ce','latch_disabled'))
        capture.append({'net':net,'source':src,'pass':ok,'register':chk})
    row['result_capture_bits']=capture
    row['checks']['232_result_bits_capture_hold_reset']={'pass':len(capture)==232 and all(c['pass'] for c in capture)}
    # ABI: 266 nonconstant bits; 54 zero-extension/reserved bits handled separately.
    abi={**{b:A+f'/publish_sequence[{b}]' for b in range(32)},32:A+'/comparison_valid',33:A+'/bbox_valid',34:A+'/publish_error'}
    abi.update({64+b:A+f'/block_word[{b}]' for b in range(8)})
    abi.update({72+b:A+f'/samples[{b}]' for b in range(15)})
    for off,field in [(96,'minx'),(100,'maxx'),(104,'miny'),(108,'maxy')]:
        abi.update({off+b:A+f'/{field}_word[{b}]' for b in range(4)})
    abi.update({128+b:A+f'/bitmap_word[{b}]' for b in range(192)})
    record=[x for x in instances.values() if x['instance'].startswith(A+'/motion_record[')]
    rr=[]
    for x in record:
        b=int(re.search(r'motion_record\[(\d+)\]',x['instance'])[1]);net=x['ports']['Q'];chk=reg_checks(net,'ddr_init_done',x['ports']['CE']);keep([x['instance']])
        controls=np.arange(8,dtype=np.uint32);cs=cols(controls,3)
        ll={A+'/strobe':cs[0],A+'/overflow':cs[1],A+'/overflow_reset':cs[2]}
        ce=test(ll,8,x['ports']['CE'],packed(((controls&1)!=0)&((controls&6)==0)))
        if not ce['pass'] and 'gap' in ce:
            boundary=drivers[x['ports']['CE']][0];keep([boundary['instance']])
            cin=boundary['ports'].get('CIN')
            if cin in drivers:keep([drivers[cin][0]['instance']])
        ok=b in abi and x['ports'].get('D')==abi[b] and chk['reset_polarity']=='TRUE' and x['parameters'].get('LCE_POL')=='FALSE' and all(chk[k] for k in ('clock','rising','async_zero','reset_net','ce','latch_disabled')) and ce['pass']
        structural=b in abi and x['ports'].get('D')==abi[b] and chk['reset_polarity']=='TRUE' and x['parameters'].get('LCE_POL')=='FALSE' and all(chk[k] for k in ('clock','rising','async_zero','reset_net','ce','latch_disabled'))
        rr.append({'bit':b,'net':net,'source':x['ports'].get('D'),'pass':ok,'structural_pass':structural,'capture_ce':ce,'register':chk,'ce_net':x['ports']['CE']})
    row['record_bits']=rr
    row['checks']['record_266_variable_bits_abi_capture']={'pass':len(rr)==266 and {r['bit'] for r in rr}==set(abi) and all(r['pass'] for r in rr),'expected_ce':'strobe && !overflow && !overflow_reset'}
    row['checks']['record_266_abi_clock_reset_shared_positive_ce']={'pass':len(rr)==266 and {r['bit'] for r in rr}==set(abi) and all(r['structural_pass'] for r in rr) and len({x['ports']['CE'] for x in record})==1}
    row['gaps']=sorted({r['capture_ce']['gap'] for r in rr if 'gap' in r['capture_ce']})
    rows.append(row)
    out={'status':'in_progress','run':str(RUN),'scope':'bounded publication and capture cones; work arithmetic/FIFO issue excluded','rows':rows,'evidence':evidence}
    (RUN/'publication_mapped_review.json').write_text(json.dumps(out,indent=2)+'\n')
out['status']='resolved' if all(c['pass'] for r in rows for c in r['checks'].values()) else 'precise_gaps'
out['hashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [V,RUN/'mapped_dump.txt',RUN/'inputs/source/motion/block_motion_detector.v',RUN/'inputs/source/motion/motion_stream_adapter.v',RUN/'simulation_input_binding.json',Path('log/100h_motion/four_camera_regression.json')]}
out['evidence_count']=len(evidence)
out['source_quotes']=[{'file':'inputs/source/motion/block_motion_detector.v','quote':(RUN/'inputs/source/motion/block_motion_detector.v').read_bytes().decode('gb18030').splitlines()[a-1:b]} for a,b in [(174,189),(238,255)]]
out['source_quotes'].append({'file':'inputs/source/motion/motion_stream_adapter.v','quote':(RUN/'inputs/source/motion/motion_stream_adapter.v').read_bytes().decode('gb18030').splitlines()[152:158]})
out['simulation_receipt']=json.loads(Path('log/100h_motion/four_camera_regression.json').read_text())
(RUN/'publication_mapped_review.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'status':out['status'],'checks':[{ 'camera':r['camera'],'checks':r['checks']} for r in rows]},indent=2))
```
