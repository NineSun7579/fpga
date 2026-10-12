"""Gracefully run the same reviewed binary with FPGA input disabled for paired evidence."""
import argparse,json,uuid
import deploy_candidate as d
parser=argparse.ArgumentParser();parser.add_argument('trial');args=parser.parse_args()
folder=(d.ROOT/args.trial).resolve();folder.relative_to(d.ROOT)
receipt=json.loads((folder/'receipt.json').read_text());assert receipt['phase']=='candidate_running'
session=d.Session(folder,receipt)
try:
    assert session.rpc('boot')['boot_id']==receipt['baseline']['boot_id']
    assert session.rpc('hash',path=session.helper)['sha256']==receipt['artifacts']['helper_sha256']
    session.rpc('verify_lock',remote=session.remote)
    current=receipt['candidate']
    session.rpc('stop',identity=current['identity'],env=current['env'],status=current['status'])
    session.save('input_on_retired',input_on_candidate=current)
    baseline=receipt['baseline'];env=dict(current['env'])
    env[receipt['arguments']['feature_env']]='0'
    env.pop(receipt['arguments']['verify_env'],None)
    run='candidate-off-'+uuid.uuid4().hex
    paths={key:session.remote+'/'+run+suffix for key,suffix in
           {'config':'.launch.json','log':'.viewer.log','supervisor_log':'.supervisor.log',
            'identity_file':'.identity.json','status':'.exit.json'}.items()}
    exe=receipt['arguments']['viewer_remote']
    argv=list(baseline['argv']);argv[0]=exe
    assert receipt['arguments']['viewer_args_json'] is None
    identity=session.rpc('launch',exe=exe,sha256=receipt['arguments']['viewer_sha256'],argv=argv,env=env,
                         cwd=baseline['cwd'],uid=baseline['uid'],gid=baseline['gid'],groups=baseline['groups'],
                         candidate=True,**paths)
    session.save('candidate_running',candidate={'identity':identity,'env':env,**paths},input_mode='OFF')
    print(json.dumps(identity))
finally:session.client.close()
