from run_sim import HERE,RTL,MS,VENDOR,command,mem,layout,words
import json


def compile_run(d,sources,top,marker):
    d.mkdir(exist_ok=True)
    command([MS/'vlib.exe','work'],d,'vlib')
    command([MS/'vlog.exe','-quiet','-work','work',*sources],d,'compile')
    s=command([MS/'vsim.exe','-c','-quiet','-wlf','contract.wlf','-l','transcript.log',
               'work.'+top,'-do','run -all; quit -f'],d,'simulate')
    if marker not in s:raise RuntimeError('missing '+marker)


def buffers():
    d=HERE/'buffers';d.mkdir(exist_ok=True)
    expected=[int.from_bytes(bytes((17*i+11*l)%256 for l in range(16)),'little') for i in range(12)]
    mem(d/'input_words.mem',expected)
    compile_run(d,[RTL/'common/spram.v',RTL/'conv/conv_in_buf.v',RTL/'conv11_16/conv11_in_buf.v',HERE/'tb_contract_buffers.v'],
                'tb_contract_buffers','CONTRACT_BUFFERS_DONE')
    rows=[l.split() for l in (d/'buffers_observed.txt').read_text().splitlines()]
    result={}
    for tag in ('B','J'):
        r=[x for x in rows if x[0]==tag]
        known=all(x[2] in {'0','1'} and x[3] in {'0','1'} and (x[2]=='0' or not any(c in x[4].lower() for c in 'xz')) for x in r)
        actual=[int(x[4],16) for x in r if x[2]=='1' and not any(c in x[4].lower() for c in 'xz')]
        lasts=[i for i,x in enumerate(r) if x[3]=='1']
        result[tag]=dict(expected_words=12,actual_words=len(actual),known=known,last_indices=lasts,
                         pass_exact=known and actual==expected and lasts==[11] and all(x[2]=='1' for x in r))
    (d/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('buffers',result,flush=True)
    return result


def multiplier():
    d=HERE/'mul_fullrange'
    compile_run(d,[VENDOR/'GTP_GRS.v',VENDOR/'GTP_APM_E2.v',RTL/'conv/conv_mul_E2.v',RTL/'conv11_16/conv11_mul_E2.v',HERE/'tb_contract_mul.v'],
                'tb_contract_mul','CONTRACT_MUL_DONE')
    rows=[l.split() for l in (d/'mul_observed.txt').read_text().splitlines()]
    # Record input IDs at the sampling posedge, then outputs after NBA. For a
    # pipeline of D registers, input sampled on edge n emerges on n+D-1.
    indexed={int(r[0]):r[2:] for r in rows}
    sampling={int(r[1]):int(r[0]) for r in rows if int(r[1])>=0}
    results={}
    for delay in (3,4):
        bad=[]
        for i in range(65536):
            a=i//256;a=a-256 if a>=128 else a
            b=~(i//256)&255;b=b-256 if b>=128 else b
            c=i%256
            expected=[f'{a*c&65535:04x}',f'{b*c&65535:04x}']*2
            got=indexed.get(sampling[i]+delay-1)
            if got!=expected:bad.append(dict(index=i,got=got,expected=expected))
        results[str(delay)]=dict(expected_words=65536,mismatch_count=len(bad),first_mismatches=bad[:4],pass_exact=not bad)
    (d/'result.json').write_text(json.dumps(results,indent=2)+'\n')
    print('multiplier',[('delay'+k,v['mismatch_count']) for k,v in results.items()],flush=True)
    return results


def accumulation():
    d=HERE/'add_bias';d.mkdir(exist_ok=True)
    biases=[9*65536,-35*65536,81*65536]+[0]*13
    packed=layout.pack_biases(biases[:3],16)
    bp=[int.from_bytes(packed[i:i+4],'little') | int.from_bytes(packed[i+8:i+12],'little')<<32 for i in range(0,128,16)]
    mem(d/'bias_pairs.mem',bp,16)
    partial=[];expected=[]
    for g in range(8):
        values=[]
        for part in range(2):
            row=[]
            for x in range(16):
                lanes=[256*(x-8+lane*2+part*3) if g*2+lane<3 else 0 for lane in range(2)]
                row.append(lanes)
                partial.append((lanes[0]&0xffffff) | (lanes[1]&0xffffff)<<24)
            values.append(row)
        for x in range(16):
            out=[]
            for lane in range(2):
                s=values[0][x][lane]+values[1][x][lane]
                q16=s*256+biases[g*2+lane]+128*65536
                out.append(max(0,min(255,(q16+32768)//65536)))
            expected.append(out[0]|out[1]<<8)
    mem(d/'partial_rows.mem',partial,12);mem(d/'expected.mem',expected,4)
    compile_run(d,[RTL/'common/spram.v',RTL/'common/scale_mul_s3.v',RTL/'conv/conv_add.v',RTL/'conv11_16/conv11_add.v',HERE/'tb_contract_add.v'],
                'tb_contract_add','CONTRACT_ADD_DONE')
    rows=[l.split() for l in (d/'add_observed.txt').read_text().splitlines()]
    results={}
    for tag in ('A','J'):
        r=[x for x in rows if x[0]==tag]
        unknown=[x for x in r if x[2] not in {'0','1'} or x[3] not in {'0','1'} or (x[2]=='1' and any(c in x[4].lower() for c in 'xz'))]
        actual=[int(x[4],16) for x in r if x[2]=='1' and not any(c in x[4].lower() for c in 'xz')]
        lasts=[i for i,x in enumerate(r) if x[3]=='1']
        mismatch=[dict(index=i,got=f'{a:04x}',expected=f'{e:04x}') for i,(a,e) in enumerate(zip(actual,expected)) if a!=e]
        results[tag]=dict(expected_words=len(expected),actual_words=len(actual),unknown_events=unknown,
                          mismatch_count=len(mismatch),first_mismatches=mismatch[:5],last_indices=lasts,
                          pass_exact=not unknown and actual==expected and lasts==list(range(15,128,16)))
    (d/'result.json').write_text(json.dumps(results,indent=2)+'\n')
    print('accumulation',results,flush=True)
    return results


if __name__=='__main__':
    results=dict(buffers=buffers(),multiplier=multiplier(),accumulation=accumulation())
    (HERE/'unit_results.json').write_text(json.dumps(results,indent=2)+'\n')
    if not (all(r['pass_exact'] for r in results['buffers'].values()) and results['multiplier']['3']['pass_exact']
            and all(r['pass_exact'] for r in results['accumulation'].values())):raise SystemExit(1)
