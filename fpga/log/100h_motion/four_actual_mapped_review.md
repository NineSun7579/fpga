# Four-camera actual mapped pipeline review — run 212303

Review completed with specific unresolved operator boundaries. Only current-run frozen sources and vendor exports are used. Machine-readable results and 4,875 verified literal evidence entries are in `project/motion_100h/run_20261003_212303/pipeline_mapped_review.json`.

| Finding | CAM1 | CAM2 | CAM3 | CAM4 |
|---|---:|---:|---:|---:|
| 19200x8 history / attributed DRM36K | 8 | 8 | 8 | 8 |
| READ_BEFORE_WRITE, shared 15-bit address, QA history and DA luma routing | pass | pass | pass | pass |
| Decision/metadata register bits | 202 | 202 | 202 | 202 |
| All 192 full-eight-bit select equality functions | pass | pass | pass | pass |
| changed_q = compare_enabled AND difference>=16 | pass | pass | pass | pass |
| Eight unconditional registered coordinate transfers | pass | pass | pass | pass |
| update_pending = !core_start AND compare_pending | pass | pass | pass | pass |
| All 192 four-bit counter next-state functions | pass | pass | pass | pass |
| Bitmap next-state functions decoded successfully | 191/192 | 191/192 | 191/192 | 191/192 |
| Registered adapter tuple bits, axi_clk, async zero reset | 19 | 19 | 19 | 19 |
| RGB/end tuple data relative to mapped flush N77 | pass | pass | pass | pass |
| Full RGB/end tuple flush predicate | unresolved | pass | unresolved | unresolved |

Exactly four history groups and 32 DRM36K slices were independently extracted from the current ADIF. No mapped `u_cam5_motion` or `u_cam6_motion` detector instances were found. The decision count is 192 select bits, eight coordinate bits, changed_q and update_pending. All have rising axi_clk, no clock enable, asynchronous reset to zero through N1615. The select evaluator checks all 256 block_q values, including invalid values 192..255. Coordinate D pins use block_q[3:0] and block_q[7:4]; these are the mapped aliases of captured bx_q/by_q and must be interpreted with the frozen sample_block packing.

All 768 counter bits per camera have clock/reset evidence. Each counter next-state was evaluated over 2,048 combinations of its old four-bit count and seven controls. Every counter matches clear-first priority, increment only on update_pending && changed_q && select_q && count<8, saturation at 8, and otherwise hold. Bitmap functions were evaluated for both old bitmap states over the same domain. One bitmap per camera reaches a gopA operator: CAM1 bit 145 (N9386_3), CAM2 bit 74 (N11978_3), CAM3 bit 146 (N9578_3), CAM4 bit 68 (N12122_3). These are evaluator boundaries, not observed mismatches.

The mapped chain is consistent with sample acceptance at S, registered decision/destination at S+1, and qualified local work at S+2. The mapped end_pending/publish_pending pair shares a gopLUT6QQ with FFAPPMUX_SEL=SRQ; result strobe takes publish_pending through its D pin. This establishes the two registered publication edges after an asserted end_pending. Full complete-frame qualification and every publication capture gate are still outside the completed function checks, so the report does not claim full end/restart/result equivalence.

The remaining actionable checks are:

- Decode gopA/gopAL6Q arithmetic semantics for RGB565-to-luma and absolute difference; changed_q's threshold function is proven relative to the actual difference bus, not a newly proven arithmetic implementation.
- Resolve the four named bitmap gopA Y cones above. Their full primitive quotes are retained.
- Validate core_start/core_valid complete predicate cones. CAM1/3/4 mapped flush N77 uses gopA MODE=XOR; CAM2's ordinary LUT cone already matches overflow OR overflow_reset. All 16 RGB bits and core_end match their source data relative to N77, and all 19 tuple bits share the required clock/reset boundary.
- Validate complete-frame end qualification, all result capture enables, bbox/snapshot functions if full result equivalence is required. The two-edge shift/strobe connection alone does not establish these functions.

The separate `control_mapped_review.json` reports N1615/reset and N63/enable resolved, including CAM2's L5 enable output. Its dump/source hashes match this review's hashes. Parent is validating that control evidence independently; this report retains its own operator boundaries without treating them as RTL defects. `accepted` remains false because the combined resource review belongs to the parent.

The executable extraction below is retained to make the numeric LUT checks reproducible. It reads files and prints results; it does not invoke vendor tools or write the parent audit. Scalar LUT6 uses INIT indexed by I0..I5; dual LUT cells use upper/lower 32-bit halves for L6/L5. Arithmetic/carry operators are deliberately unsupported in this evaluator and are reported as gaps rather than decoded as ordinary LUTs.

```python
from pathlib import Path
import re, json, hashlib
from collections import Counter
RUN = Path('project/motion_100h/run_20261003_212303')
V = RUN / 'mapped_dump.v'
raw = V.read_bytes()
source = raw.decode('gb18030', errors='replace')
pattern = re.compile(r'(?m)^\s*(gop\w+)\s*/\*\s*(.*?)\s*\*/\s*#\((.*?)\)\s*\\[^\n]+?\s*\((.*?)\);', re.S)
def norm(value):
    return re.sub(r'\s+', '', value).lstrip('\\')
instances = {}
drivers = {}
for match in pattern.finditer(source):
    kind, name, params, ports = match.group(1,2,3,4)
    name = name.lstrip('\\')
    p = {k: v.strip().strip('"') for k,v in re.findall(r'\.(\w+)\(([^()]*)\)',params)}
    c = {k: norm(v) for k,v in re.findall(r'\.(\w+)\s*\(([^()]*)\)',ports)}
    item = {'instance': name, 'kind': kind, 'parameters': p, 'ports': c, 'quote': match.group()}
    instances[name] = item
    for pin in ('L6','L5','L6Q','L5Q','L6QQ','Q','Y','COUT'):
        if c.get(pin):
            if c[pin] in drivers:
                raise ValueError('multiple drivers: '+c[pin])
            drivers[c[pin]] = (item,pin)
def init(item):
    value = item['parameters'].get('INIT','')
    m = re.fullmatch(r"(\d+)'b([01]+)",value)
    if not m: raise ValueError('unsupported INIT '+item['instance'])
    return int(m[2],2)
def table(item,pin):
    kind,p = item['kind'],item['parameters']
    if p.get('MODE') != 'LUT6': raise ValueError('arithmetic/operator boundary '+item['instance']+':'+pin)
    if kind in ('gopLUT6','gopLUT6Q','gopLUT6QQ'):
        if pin not in ('L6','L6Q'):raise ValueError('unsupported scalar pin '+pin)
        return init(item),6
    if kind in ('gopLUT6L5','gopLUT6L5Q','gopLUT6QL5','gopLUT6QL5Q','gopLUT6L5Q1','gopLUT6QL5Q1'):
        if pin in ('L6','L6Q'):return init(item)>>32,5
        if pin in ('L5','L5Q'):return init(item)&0xffffffff,5
    raise ValueError('unsupported packed operator '+kind+':'+pin)
def apply_table(item,pin,evaluate,mask):
    t,bits = table(item,pin)
    dependent = [any(((t>>index)&1)!=((t>>(index^(1<<bit)))&1) for index in range(1<<bits)) for bit in range(bits)]
    values = [evaluate(item['ports'].get('I'+str(i),"1'bx")) if dependent[i] else 0 for i in range(bits)]
    result=0
    for index in range(1<<bits):
        if not (t>>index)&1:continue
        term=mask
        for bit,value in enumerate(values):term &= value if (index>>bit)&1 else mask^value
        result |= term
    return result
def next_data(net,evaluate,mask):
    item,pin=drivers[net];p=item['parameters'];c=item['ports']
    if pin=='Q' and item['kind']=='gopQ' and p.get('QMUX_SEL')=='MX':return evaluate(c['D'])
    if pin=='L6QQ' and p.get('FFAPPMUX_SEL')=='SRQ':return evaluate(c['L6Q'])
    mux = 'FFAPPMUX_SEL' if pin=='L5Q' else 'QMUX_SEL'
    if p.get(mux)!='YX':raise ValueError('unsupported FF mux '+item['instance']+':'+pin)
    return apply_table(item,pin,evaluate,mask)
def evaluator(leaves,n):
    mask=(1<<n)-1;memo=dict(leaves);used=set();unknown=set()
    def evaluate(net):
        if net in memo:return memo[net]
        if net in ("1'b0",''):return 0
        if net=="1'b1":return mask
        if net=="1'bx":unknown.add(net);return 0
        if net not in drivers:raise ValueError('no driver '+net)
        item,pin=drivers[net];used.add(item['instance'])
        if pin in ('Q','L6Q','L5Q','L6QQ'):raise ValueError('unprovided registered leaf '+net)
        value=apply_table(item,pin,evaluate,mask);memo[net]=value;return value
    return evaluate,mask,used
def column(values,bit):return sum(((value>>bit)&1)<<i for i,value in enumerate(values))
def reg_checks(net,reset,ce=None):
    item,pin=drivers[net];p,c=item['parameters'],item['ports']
    app=pin in ('L5Q','L6QQ');ff='FFAPP_' if app else 'FF_'
    return {'clock':c.get('CLK')=='axi_clk','rising':p.get('CLK_POL')=='FALSE',
        'async_zero':p.get('RS_MODE')=='ASYNC' and p.get(ff+'RS')=='RESET' and p.get(ff+'INIT')=="1'b0",
        'reset_net':c.get('RS')==reset,'reset_polarity':p.get('LRS_POL'),
        'ce':p.get('LCE_EN')==('TRUE' if ce else 'FALSE') and (not ce or c.get('CE')==ce),
        'latch_disabled':p.get('LATCH_EN')=='FALSE','kind':item['kind'],'pin':pin,'instance':item['instance']}
DS=['ov5640_top/u_motion_tap/u_detector']+[f'cam{i}_ov5640_top/u_motion_tap/u_detector' for i in (2,3,4)]
rows=[]
all_evidence={}
def retain(names):
    for name in names:
        x=instances[name]
        all_evidence[name]={'file':'mapped_dump.v','sha256':hashlib.sha256(raw).hexdigest(),'quote':x['quote']}
for D in DS:
    A=D.rsplit('/u_detector',1)[0]
    row={'detector':D,'checks':{},'unresolved':[],'inventory':{}}
    reset=drivers[D+'/changed_q'][0]['ports']['RS']
    row['reset_net']=reset
    ev,mask,used=evaluator({'ddr_init_done':column(range(4),0),A+'/overflow_reset':column(range(4),1)},4)
    try:row['checks']['reset_function']=ev(reset)==column([1,0,1,1],0)
    except ValueError as err:row['unresolved'].append(str(err))
    retain(used)
    decision=[D+'/update_pending',D+'/changed_q']+[D+f'/select_q[{i}]' for i in range(192)]+[D+f'/update_b{axis}[{i}]' for axis in ('x','y') for i in range(4)]
    row['inventory']['decision_bits']=len([net for net in decision if net in drivers])
    checks=[reg_checks(net,reset) for net in decision if net in drivers]
    row['checks']['decision_202_registers']=len(checks)==202 and all(all(x[k] for k in ('clock','rising','async_zero','reset_net','ce','latch_disabled')) and x['reset_polarity']=='FALSE' for x in checks)
    retain(x['instance'] for x in checks)
    row['inventory']['select_indices']=[i for i in range(192) if D+f'/select_q[{i}]' in drivers]
    leaves={D+f'/block_q[{bit}]':column(range(256),bit) for bit in range(8)}
    ev,mask,used=evaluator(leaves,256);bad=[]
    for i in range(192):
        try:
            if next_data(D+f'/select_q[{i}]',ev,mask)!=(1<<i):bad.append(i)
        except ValueError as err:bad.append([i,str(err)])
    row['checks']['select_all_192_equality_truth_tables']=not bad;row['select_failures']=bad[:5];retain(used)
    leaves={D+'/compare_enabled':column(range(32),0),**{D+f'/difference[{bit+4}]':column(range(32),bit+1) for bit in range(4)}}
    ev,mask,used=evaluator(leaves,32)
    try:row['checks']['changed_q_threshold_truth']=next_data(D+'/changed_q',ev,mask)==sum((bool(i&1) and bool(i>>1))<<i for i in range(32))
    except ValueError as err:row['unresolved'].append(str(err))
    retain(used)
    row['coordinate_inputs']={}
    for axis,base in [('x',0),('y',4)]:
        for bit in range(4):
            net=D+f'/update_b{axis}[{bit}]';x,pin=drivers[net]
            row['coordinate_inputs'][net]=x['ports'].get('D')
    row['checks']['coordinate_transfer_8_bits']=all(value==D+f'/block_q[{bit+base}]' for axis,base in [('x',0),('y',4)] for bit in range(4) for value in [row['coordinate_inputs'][D+f'/update_b{axis}[{bit}]']])
    leaves={A+'/core_start':column(range(4),0),D+'/compare_pending':column(range(4),1),D+'/accept_sample':0}
    ev,mask,used=evaluator(leaves,4)
    try:row['checks']['update_pending_frame_start_priority']=next_data(D+'/update_pending',ev,mask)==4
    except ValueError as err:row['unresolved'].append(str(err))
    retain(used)
    row['publication_registers']={}
    for net in [D+'/end_pending',D+'/publish_pending',A+'/strobe']:
        x,pin=drivers[net];row['publication_registers'][net]={'instance':x['instance'],'pin':pin,'parameters':x['parameters'],'ports':x['ports']};retain([x['instance']])
    x,pin=drivers[D+'/publish_pending'];y,ypin=drivers[D+'/end_pending'];z,zpin=drivers[A+'/strobe']
    row['checks']['end_to_publish_shift_plus_strobe']=x is y and pin=='L6QQ' and ypin=='L6Q' and x['parameters'].get('FFAPPMUX_SEL')=='SRQ' and z['ports'].get('D')==D+'/publish_pending'
    tuples=[A+'/core_start',A+'/core_end',A+'/core_valid']+[A+f'/core_rgb[{i}]' for i in range(16)]
    row['inventory']['adapter_tuple_bits']=len([net for net in tuples if net in drivers])
    tchecks=[reg_checks(net,'ddr_init_done') for net in tuples if net in drivers]
    row['checks']['adapter_tuple_19_registers']=len(tchecks)==19 and all(all(x[k] for k in ('clock','rising','async_zero','reset_net','ce','latch_disabled')) and x['reset_polarity']=='TRUE' for x in tchecks);retain(x['instance'] for x in tchecks)
    row['adapter_tuple_drivers']={net:{'instance':drivers[net][0]['instance'],'pin':drivers[net][1],'ports':drivers[net][0]['ports'],'parameters':drivers[net][0]['parameters']} for net in tuples}
    leaves={A+'/head[0]':column(range(16),0),A+'/end_pending':column(range(16),1),A+'/overflow':column(range(16),2),A+'/overflow_reset':column(range(16),3)}
    # Trace flush guards through named overflow leaves; evaluate every RGB bit separately.
    tuple_results={}
    for net in tuples:
        row_leaves={A+'/overflow':column(range(8),0),A+'/overflow_reset':column(range(8),1), 'ddr_init_done':255}
        for bit in range(18):row_leaves[A+f'/head[{bit}]']=0
        expected=None
        if '/core_rgb[' in net:
            bit=int(re.search(r'\[(\d+)\]$',net)[1]);row_leaves[A+f'/head[{bit}]']=column(range(8),2);expected=sum((bool(i&4) and not(i&3))<<i for i in range(8))
        elif net.endswith('/core_end'):
            row_leaves[A+'/end_pending']=column(range(8),2);expected=sum((bool(i&4) and not(i&3))<<i for i in range(8))
        if expected is not None:
            ev,mask,used=evaluator(row_leaves,8)
            try:tuple_results[net]=next_data(net,ev,mask)==expected
            except ValueError as err:tuple_results[net]=str(err)
            retain(used)
    row['adapter_tuple_data_tests']=tuple_results
    row['checks']['adapter_16_rgb_and_end_flush_data']=len(tuple_results)==17 and all(v is True for v in tuple_results.values())
    # Independently test tuple data relative to the *actual* mapped flush net.
    # This does not prove the arithmetic cell generating that flush net.
    row['tuple_data_relative_to_mapped_flush']={}
    for net in tuples:
        leaves={A+'/N77':column(range(4),0),'ddr_init_done':15}
        for bit in range(18):leaves[A+f'/head[{bit}]']=0
        if '/core_rgb[' in net:
            bit=int(re.search(r'\[(\d+)\]$',net)[1]);leaves[A+f'/head[{bit}]']=column(range(4),1)
        elif net.endswith('/core_end'):leaves[A+'/end_pending']=column(range(4),1)
        else:continue
        ev,mask,used=evaluator(leaves,4)
        try:row['tuple_data_relative_to_mapped_flush'][net]=next_data(net,ev,mask)==4
        except ValueError as err:row['tuple_data_relative_to_mapped_flush'][net]=str(err)
        retain(used)
    if A+'/N77' in drivers:retain([drivers[A+'/N77'][0]['instance']])
    # Count all local counter/bitmap bits, including distinct packed FF outputs.
    counters=[D+f'/block_hits[{b}][{bit}]' for b in range(192) for bit in range(4)]
    row['inventory']['local_counter_bits']=sum(net in drivers for net in counters)
    row['inventory']['bitmap_work_bits']=sum(D+f'/bitmap_work[{b}]' in drivers for b in range(192))
    retain(drivers[net][0]['instance'] for net in counters if net in drivers)
    row['local_counter_register_clock_reset_checks']=all(
        all(reg_checks(net,reset,drivers[net][0]['ports'].get('CE'))[k] for k in ('clock','rising','async_zero','reset_net','latch_disabled'))
        for net in counters if net in drivers)
    row['checks']['all_768_local_counter_bits']=row['inventory']['local_counter_bits']==768 and row['local_counter_register_clock_reset_checks']
    row['local_counter_data_boundaries']={}
    for b in (0,1,191):
        for bit in range(4):
            net=D+f'/block_hits[{b}][{bit}]'
            if net in drivers:
                x,pin=drivers[net];row['local_counter_data_boundaries'][net]={'instance':x['instance'],'pin':pin,'ports':x['ports'],'parameters':x['parameters']}
    # Exhaustive local next-state check: 16 counts x 128 control combinations.
    values=list(range(2048));control_names=['update_pending','changed_q','select','frame_start','end_pending','publish_pending','clear_after_publish']
    columns=[column(values,j) for j in range(11)]
    expected=[];bitmap_expected=[0,0]
    for val in values:
        count=val&15;u,ch,sel,fs,end,pub,clear=[bool(val&(1<<(j+4))) for j in range(7)]
        C=(fs and not end) or (pub and clear)
        expected.append(0 if C else count+1 if u and ch and sel and count<8 else count)
        for old in (0,1):bitmap_expected[old]|=(False if C else bool(old or (u and ch and sel and count==7)))<<val
    expected_columns=[column(expected,bit) for bit in range(4)]
    counter_failures=[];bitmap_failures=[]
    for b in range(192):
        leaves={D+f'/block_hits[{b}][{bit}]':columns[bit] for bit in range(4)}
        for j,key in enumerate(control_names):
            net=A+'/core_start' if key=='frame_start' else D+(f'/select_q[{b}]' if key=='select' else '/'+key)
            leaves[net]=columns[j+4]
        ev,mask,used=evaluator(leaves,2048)
        try:
            for bit in range(4):
                net=D+f'/block_hits[{b}][{bit}]';x,pin=drivers[net];data=next_data(net,ev,mask)
                ce=ev(x['ports']['CE']) if x['parameters'].get('LCE_EN')=='TRUE' else mask
                if x['parameters'].get('LCE_POL')=='TRUE':ce^=mask
                actual=(data&ce)|(leaves[net]&(mask^ce))
                if actual!=expected_columns[bit]:counter_failures.append([b,bit,'truth mismatch'])
        except ValueError as err:counter_failures.append([b,str(err)])
        retain(used)
        # Bitmap test extends the same domain with both old bitmap values.
        for old in (0,1):
            net=D+f'/bitmap_work[{b}]';leaves[net]=mask if old else 0
            ev,mask,used=evaluator(leaves,2048)
            expect=bitmap_expected[old]
            try:
                x,pin=drivers[net];data=next_data(net,ev,mask);ce=ev(x['ports']['CE']) if x['parameters'].get('LCE_EN')=='TRUE' else mask
                if x['parameters'].get('LCE_POL')=='TRUE':ce^=mask
                if ((data&ce)|(leaves[net]&(mask^ce)))!=expect:bitmap_failures.append([b,old,'truth mismatch'])
            except ValueError as err:bitmap_failures.append([b,old,str(err)])
            retain(used);retain([drivers[net][0]['instance']])
    row['checks']['all_192_local_counter_next_states']=not counter_failures
    row['checks']['all_192_bitmap_next_states']=not bitmap_failures
    row['counter_failures']=counter_failures
    row['bitmap_failures']=bitmap_failures
    rows.append(row)
out={'run':str(RUN),'mapped_verilog_sha256':hashlib.sha256(raw).hexdigest(),'rows':rows,'evidence_count':len(all_evidence),'instances_parsed':len(instances)}
print(json.dumps(out,indent=2))
```
