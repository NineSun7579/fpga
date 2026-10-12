"""Restart one parity-approved binary for a bounded lead/OFF paired trial."""
import argparse,json,uuid,re
import deploy_candidate as d

def paired_count(text):
    if re.search(r'\[scheme2-verify[^\]]*\].*\bFAIL\b',text):
        raise ValueError('Verification failure in preserved evidence')
    def identities(kind):
        result=set()
        for line in text.splitlines():
            if line.startswith('[scheme2-verify-'+kind+'] PASS '):
                fields=dict(re.findall(r'(\w+)=(\S+)',line))
                if kind=='output' and fields.get('exact')!='1':continue
                result.add(tuple(fields[key] for key in ('camera','tag','count')))
        return result
    return len(identities('input') & identities('output'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('trial')
    parser.add_argument('--lead-ms',type=int,choices=range(121),default=30,metavar='0..120')
    parser.add_argument('--input-off',action='store_true')
    args=parser.parse_args()
    folder=(d.ROOT/args.trial).resolve();folder.relative_to(d.ROOT)
    receipt=json.loads((folder/'receipt.json').read_text())
    assert receipt['phase']=='candidate_running'
    assert receipt['arguments']['verify'] is False,'Use parity-approved performance restart first'
    assert paired_count((folder/'candidate_runtime.log').read_text())>=30
    current=receipt['candidate'];baseline=receipt['baseline']
    env=dict(current['env'])
    env[receipt['arguments']['feature_env']]='0' if args.input_off else '1'
    env['DETVIEW_FPGA_PREFETCH_LEAD_MS']=str(args.lead_ms)
    verify_env=receipt['arguments']['verify_env']
    if verify_env:env.pop(verify_env,None)
    exe=receipt['arguments']['viewer_remote']
    argv=[exe]+json.loads(receipt['arguments']['viewer_args_json']) if receipt['arguments']['viewer_args_json'] is not None else [exe]+baseline['argv'][1:]
    session=d.Session(folder,receipt)
    try:
        assert session.rpc('boot')['boot_id']==baseline['boot_id']
        assert session.rpc('hash',path=session.helper)['sha256']==receipt['artifacts']['helper_sha256']
        session.rpc('verify_lock',remote=session.remote)
        assert session.rpc('hash',path=exe)['sha256']==receipt['arguments']['viewer_sha256']
        session.rpc('stop',identity=current['identity'],env=current['env'],status=current['status'])
        retired=list(receipt.get('retired_trial_runs',[]));retired.append(current)
        session.save('smoke_stopped',retired_trial_runs=retired)
        run='candidate-lead-'+uuid.uuid4().hex
        paths={key:session.remote+'/'+run+suffix for key,suffix in
               {'config':'.launch.json','log':'.viewer.log','supervisor_log':'.supervisor.log',
                'identity_file':'.identity.json','status':'.exit.json'}.items()}
        identity=session.rpc('launch',exe=exe,sha256=receipt['arguments']['viewer_sha256'],argv=argv,
                             env=env,cwd=baseline['cwd'],uid=baseline['uid'],gid=baseline['gid'],
                             groups=baseline['groups'],candidate=True,**paths)
        session.save('candidate_running',candidate={'identity':identity,'env':env,**paths},
                     input_mode='OFF' if args.input_off else 'ON',prefetch_lead_ms=args.lead_ms)
        print(json.dumps(identity))
    finally:session.client.close()

if __name__=='__main__':main()
