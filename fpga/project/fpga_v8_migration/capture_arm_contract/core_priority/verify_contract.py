"""Independent bus/memory oracle plus exact software/FPGA input pairs."""
from collections import Counter, deque
import hashlib
import json
from run_tests import source_pixels, software_prepare

BANKS=(0x01800000,0x01a00000)
OUTPUTS=(0x08000000,0x08200000)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(directory,c):
    raw_len=c['width']*c['height']*2
    out_len=c['width']*c['out']*3
    count=Counter()
    fixtures={}
    def fixture(seed):
        if seed not in fixtures:fixtures[seed]=source_pixels(c,seed)
        return fixtures[seed]
    frames={}
    source_banks=[None,None]
    frozen={}
    generation=0
    capture=None
    preparation=None
    prepared_cache={}
    output_records_live=[None,None]
    output_host=None
    ack_stage=[0,0,0]
    front_writes=[]
    front_reads=[]
    active_write=None
    active_read=None
    pending_b=None
    front_memory={}
    trace_lines=(directory/'contract_trace.txt').read_text().splitlines()
    for number,line in enumerate(trace_lines,1):
        a=line.split();tag=a[0];count[tag]+=1
        def check(ok,message):
            if not ok:raise AssertionError(f'contract:{number} {line}: {message}')
        if tag=='RESET':
            source_banks=[None,None];frozen={};capture=None;preparation=None;active_write=None;active_read=None
            pending_b=None
            output_records_live=[None,None];output_host=None;ack_stage=[0,0,0]
            front_writes.append(('RESET',));front_reads.append(('RESET',))
        elif tag=='ARM':generation=int(a[1])
        elif tag=='FRAME': pass
        elif tag=='ADMIT':
            bank,seed,gen=map(int,a[1:]);check(source_banks[bank] is None,'admitted into existing RAW lease')
            capture=dict(bank=bank,seed=seed,gen=gen,claimed=set(),released=set(),
                         source=fixture(seed))
            source_banks[bank]=capture
        elif tag=='PUBLISH':
            bank,seq,gen,seed=map(int,a[1:]);key=(gen,seq)
            check(capture is not None and (bank,seed,gen)==(capture['bank'],capture['seed'],capture['gen']),'publish identity/source')
            check(key not in frames,'identity reused')
            source=capture['source'];expected=source+seq.to_bytes(4,'little')+bytes(12)
            path=directory/f'g{gen}_s{seq}_completed_raw.bin'
            check(path.read_bytes()==expected,'actual completed RAW/tag differs from sensor fixture')
            image=b''.join(front_memory.get(BANKS[bank]+i,bytes([0xa5])*16) for i in range(0,raw_len+16,16))
            check(image==expected,'front W stream did not write full certified source/tag')
            capture.update(seq=seq,key=key,expected=expected)
            frames[key]=capture;frozen[bank]=expected;capture=None
        elif tag in ['COOP_CLAIM','RAW_CLAIM']:
            bank,seq,gen=int(a[1]),int(a[2]),int(a[3]);token=int(a[4],16)
            record=source_banks[bank];consumer='C' if tag=='COOP_CLAIM' else 'H'
            check(record and record.get('key')==(gen,seq) and token==(gen<<32)|seq,'claim stale/wrong identity')
            check(consumer not in record['claimed'],'duplicate claim')
            record['claimed'].add(consumer)
            if consumer=='C':
                preparation=record
                free=next((i for i,entry in enumerate(output_records_live) if entry is None),None)
                check(free is not None,'core accepted descriptor without a FREE output bank')
                output_records_live[free]=dict(record=record,state='WRITING')
                record['output_bank']=free
                if record['seed'] not in prepared_cache:
                    prepared_cache[record['seed']]=software_prepare(record['source'],c)
        elif tag in ['COOP_RELEASE','RAW_RELEASE']:
            bank,seq,gen=int(a[1]),int(a[2]),int(a[3]);token=int(a[4],16)
            consumer='C' if tag=='COOP_RELEASE' else 'H';record=source_banks[bank]
            match=bool(record and record.get('key')==(gen,seq) and token==(gen<<32)|seq
                       and consumer in record['claimed'] and consumer not in record['released'])
            if tag=='RAW_RELEASE':
                check((int(a[5]),int(a[6]))==(int(match),int(not match)),'host release result')
            else:check(match,'real bridge source release did not match manager lease')
            if match:
                record['released'].add(consumer)
                if record['released']=={'C','H'}:
                    image=b''.join(front_memory.get(BANKS[bank]+i,bytes([0xa5])*16) for i in range(0,raw_len+16,16))
                    check(image==frozen[bank],'frozen source overwritten before both releases')
                    del frozen[bank];source_banks[bank]=None
        elif tag=='AW':
            address,ident,beats=int(a[1],16),int(a[2]),int(a[3])
            check(active_write is None and 1<=beats<=16 and address%16==0,'front AW obligations/shape')
            check(pending_b is None,'front AW before prior B retirement')
            check((address&4095)+beats*16<=4096,'4KiB crossing')
            for bank in frozen:check(not BANKS[bank]<=address<BANKS[bank]+raw_len+16,'AW targets held RAW')
            if ident==1:
                outbank=next((i for i,b in enumerate(OUTPUTS) if b<=address<b+out_len),None)
                check(outbank is not None and output_records_live[outbank]
                      and output_records_live[outbank]['state']=='WRITING','AW targets retained output')
            active_write=dict(address=address,id=ident,left=beats)
            pending_b=ident
        elif tag=='W':
            address,ident,word,strobe,last=int(a[1],16),int(a[2]),int(a[3],16),int(a[4],16),int(a[5])
            check(active_write and (address,ident)==(active_write['address'],active_write['id']) and last==(active_write['left']==1),'front W order/ID/last')
            value=word.to_bytes(16,'little')
            check(strobe==0xffff,'fixtures have complete aligned source/output words')
            if ident==3:
                check(capture is not None,'actual camera W without SOF reservation')
                offset=address-BANKS[capture['bank']]
                if offset==raw_len:
                    seq=word&0xffffffff;check(value==seq.to_bytes(4,'little')+bytes(12),'tag padding')
                else:
                    expected=capture['source'][offset:offset+16]
                    check(value==expected,'actual camera full 128-bit RAW word')
                count['camera_words']+=1
            elif ident==1:
                check(any(base<=address<base+out_len for base in OUTPUTS),'output address guard')
                check(preparation is not None,'bridge W without real cooperative RAW claim')
                base=OUTPUTS[1] if address>=OUTPUTS[1] else OUTPUTS[0]
                check(base==OUTPUTS[preparation['output_bank']],'bridge wrote wrong reserved output bank')
                offset=address-base
                expected=prepared_cache[preparation['seed']][offset:offset+16]
                check(value==expected,'all 128 prepared RGB888/fill bits vs independent claimed RAW golden')
                count['output_words']+=1
            else:
                owner=ident-8;base=0x00800000+owner*0x00100000;offset=address-base
                tx=offset//256;beat=(offset%256)//16
                check(owner in [0,1,2,3,5] and 0<=tx<c['bursts'],'competitor bank guard')
                expected=bytes((owner*37+tx*19+beat*11+lane*7)&255 for lane in range(16))
                check(value==expected,'all 128 competitor bits')
                count['competitor_words']+=1
            front_memory[address]=value
            front_writes.append((address,ident,word,strobe,last))
            active_write['address']+=16;active_write['left']-=1
            if last:active_write=None
        elif tag=='B':
            check(int(a[2])==0 and pending_b==int(a[1]) and active_write is None,'front B identity/last-W retirement')
            pending_b=None
        elif tag=='AR':
            address,ident,beats=int(a[1],16),int(a[2],16),int(a[3])
            check(active_read is None and ident in [0x21,6] and 1<=beats<=16,'full RID/AR ownership')
            active_read=dict(address=address,id=ident,left=beats)
        elif tag=='R':
            address,ident,word,last=int(a[1],16),int(a[2],16),int(a[3],16),int(a[4])
            check(active_read and (address,ident)==(active_read['address'],active_read['id']) and last==(active_read['left']==1),'read RID/last/held ownership')
            expected=front_memory.get(address,bytes([0xa5])*16)
            check(word.to_bytes(16,'little')==expected,'every consumed R bit vs independent memory')
            if ident==0x21:
                bank=next((i for i,b in enumerate(BANKS) if b<=address<b+raw_len),None)
                check(bank is not None and bank in frozen and 'C' in source_banks[bank]['claimed'],'core reading outside claimed RAW')
                count['core_read_words']+=1
            else:count['host_read_words']+=1
            if ident==6:
                rawbank=next((i for i,b in enumerate(BANKS) if b<=address<b+raw_len+16),None)
                outbank=next((i for i,b in enumerate(OUTPUTS) if b<=address<b+out_len),None)
                if rawbank is not None:
                    check(source_banks[rawbank] and 'H' in source_banks[rawbank]['claimed']
                          and 'H' not in source_banks[rawbank]['released'],'host R outside RAW claim')
                else:
                    check(outbank is not None and output_host==outbank and
                          output_records_live[outbank]['state']=='HOST_READING','host R outside actual output CLAIM')
            front_reads.append((address,ident&15,word,last))
            active_read['address']+=16;active_read['left']-=1
            if last:active_read=None
        elif tag=='RAW_COPY':
            bank,seq,gen=map(int,a[1:]);record=source_banks[bank]
            check(record and record.get('key')==(gen,seq) and 'H' in record['claimed']
                  and 'H' not in record['released'],'RAW copy outside native host lease')
        elif tag=='DONE':
            check(preparation is not None,'bridge done without source')
            output_records_live[preparation['output_bank']]['state']='READY'
        elif tag=='AX_COMMIT':
            address,value,response=int(a[1],16),int(a[2],16),int(a[3])
            if address==0x30:
                check(response==0 and output_host is None and output_records_live[value] and
                      output_records_live[value]['state']=='READY','AXIL CLAIM without ready output')
                output_host=value;output_records_live[value]['state']='HOST_READING'
            elif address in [0x40,0x44,0x48]:ack_stage[[0x40,0x44,0x48].index(address)]=value
            elif address==0x4c:
                expected=bool(output_host is not None and ack_stage==[output_host,
                    output_records_live[output_host]['record']['seq'],
                    output_records_live[output_host]['record']['gen']])
                check(response==(0 if expected else 2),'AXIL exact output ACK result')
                if expected:output_records_live[output_host]=None;output_host=None
        elif tag=='FROZEN':count['frozen_checks']+=1
        elif tag in ['OUTPUT_CLAIM','OUTPUT_COPY','OUTPUT_ACK','DROP','AXW','AXR','RESET_ACTIVE_AW','FINISH']:pass
        else:raise AssertionError('unknown public event '+tag)
    if any(source_banks) or any(output_records_live) or output_host is not None or pending_b is not None or active_read:
        raise AssertionError('final ownership/AXI obligations not drained')
    if count['competitor_words']!=c['bursts']*5*16*count['RESET']:
        raise AssertionError('not all five independent competitors completed each epoch')
    # Vendor FIFO outputs must exactly preserve all front W data, including all
    # 128 bits, strobes, IDs and LAST. A coordinated reset cancels only a suffix.
    physical={};vendor_writes=[];vendor_reads=[];wa=None;ra=None
    for number,line in enumerate((directory/'memory_trace.txt').read_text().splitlines(),1):
        a=line.split();tag=a[0];count['vendor_'+tag]+=1
        if tag=='RESET':wa=ra=None;vendor_writes.append(('RESET',));vendor_reads.append(('RESET',))
        elif tag=='AW':
            if wa is not None:raise AssertionError('vendor overlapping AW')
            wa=[int(a[1],16),int(a[2]),int(a[3])]
        elif tag=='W':
            item=(int(a[1],16),int(a[2]),int(a[3],16),int(a[4],16),int(a[5]))
            address,ident,word,strobe,last=item
            if wa is None or (address,ident)!=(wa[0],wa[1]) or last!=(wa[2]==1):raise AssertionError('vendor W order/WID/last')
            physical[address]=word.to_bytes(16,'little');vendor_writes.append(item)
            wa[0]+=16;wa[2]-=1
            if last:wa=None
        elif tag=='AR':
            if ra is not None:raise AssertionError('vendor overlapping AR')
            ra=[int(a[1],16),int(a[2]),int(a[3])]
        elif tag=='R':
            item=(int(a[1],16),int(a[2]),int(a[3],16),int(a[4]))
            address,ident,word,last=item
            if ra is None or (address,ident)!=(ra[0],ra[1]) or last!=(ra[2]==1):raise AssertionError('vendor R order/RID/last')
            if word.to_bytes(16,'little')!=physical.get(address,bytes([0xa5])*16):raise AssertionError('vendor R independent physical memory')
            vendor_reads.append(item);ra[0]+=16;ra[2]-=1
            if last:ra=None
        else:raise AssertionError('unknown memory event '+tag)
    def segments(items):
        parts=[]
        for item in items:
            if item==('RESET',):parts.append([])
            else:parts[-1].append(item)
        return parts
    for kind,front,vendor in [('W',front_writes,vendor_writes),('R',front_reads,vendor_reads)]:
        fs,vs=segments(front),segments(vendor)
        if len(fs)!=len(vs):raise AssertionError('reset epochs differ')
        for i,(f,v) in enumerate(zip(fs,vs)):
            if (kind=='W' and f[:len(v)]!=v) or (kind=='R' and v[:len(f)]!=f):
                raise AssertionError(f'actual FIFO {kind} complete stream mismatch epoch {i}')
            if i==len(fs)-1 and f!=v:raise AssertionError('final FIFO not drained')
    pairs=[]
    raw_records={};output_records={};cancelled=set()
    for line in (directory/'frames.txt').read_text().splitlines():
        a=line.split();key=(int(a[2]),int(a[1]))
        if a[0]=='RAW':raw_records[key]=a
        elif a[0]=='OUTPUT':output_records[key]=a
        elif a[0]=='CANCELLED':cancelled.add(key)
    if set(raw_records)!=set(frames):raise AssertionError('missing lease-bound RAW copy for published frame')
    for key,record in frames.items():
        gen,seq=key;a=raw_records[key];seed,bank=int(a[3]),int(a[4]);token=int(a[5],16)
        expected=fixture(seed)+seq.to_bytes(4,'little')+bytes(12)
        rp=directory/a[6];cp=directory/a[7]
        if rp.read_bytes()!=expected or cp.read_bytes()!=expected:raise AssertionError('complete RAW bank/copy/tag mismatch')
        raw=rp.read_bytes()[:raw_len]
        software=software_prepare(raw,c)
        fixture_software=software_prepare(fixture(seed),c)
        if software!=fixture_software:raise AssertionError('software paired fixture preparation differs')
        prefix=f'g{gen}_s{seq}'
        fixture_path=directory/f'{prefix}_source_pixels_fixture.bin'
        software_path=directory/f'{prefix}_software_preparedinput.bin'
        fixture_path.write_bytes(fixture(seed));software_path.write_bytes(software)
        pair=dict(sequence=seq,generation=gen,token64=f'{token:016x}',camera=4,source_bank=bank,
                  seed=seed,source_addr=f'{BANKS[bank]:08x}',raw_format='little-endian RGB565 followed by 16-byte tag: LE seq32 + 12 zero bytes',
                  source_pixels_bytes=raw_len,raw_file=rp.name,raw_bytes=rp.stat().st_size,
                  source_sha256=hashlib.sha256(raw).hexdigest(),raw_sha256=sha(rp),completed_raw_sha256=sha(cp),
                  fixture_file=fixture_path.name,software_prepared_file=software_path.name,
                  software_input_sha256=hashlib.sha256(software).hexdigest())
        if key in cancelled:
            pair.update(status='cancelled_by_coordinated_reset',prepared_file=None)
        else:
            if key not in output_records:raise AssertionError('published frame has no lease-bound prepared input copy')
            op=directory/output_records[key][4]
            if op.read_bytes()!=software:raise AssertionError('entire FPGA prepared NHWC RGB888 differs from exact same RAW software input')
            pair.update(status='exact_paired_input_pass',output_bank=int(output_records[key][3]),
                        prepared_file=op.name,prepared_bytes=op.stat().st_size,
                        prepared_format='row-major NHWC uint8 RGB, bit-replicated RGB565 + 114 top/bottom fill',
                        output_sha256=sha(op))
            count['paired_bytes']+=len(software);count['paired_frames']+=1
        pairs.append(pair)
    count['raw_bytes']=sum(pair['raw_bytes'] for pair in pairs)
    count['reset_cancelled_published_frames']=len(cancelled)
    if count['FINISH']!=1 or count['paired_frames']!=(3 if c['mode'] else 5):
        raise AssertionError('missing explicit completion or paired frames')
    report=dict(parameters=c,counts=dict(count),frames=pairs,all_bus_bits_known=True,
                actual_FIFO_streams_exact=True,original_read_route_shadow_exact=True,
                independently_reconstructed_source_and_memory=True,
                trace_sha256={p.name:sha(p) for p in [directory/'contract_trace.txt',directory/'memory_trace.txt',directory/'frames.txt']})
    (directory/'checker.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
