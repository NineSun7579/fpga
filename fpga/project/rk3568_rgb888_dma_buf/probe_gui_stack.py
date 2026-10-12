"""One bounded debugger snapshot; not a performance acceptance sample."""
import argparse,shlex,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
parser=argparse.ArgumentParser();parser.add_argument('pid',type=int);parser.add_argument('--all-threads',action='store_true');args=parser.parse_args()
commands=['set pagination off','set debuginfod enabled off',f'attach {args.pid}','thread apply all bt 12' if args.all_threads else 'bt 18','detach']
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'gdb -q -nx -batch '+' '.join('-ex '+shlex.quote(x) for x in commands),timeout=25,sudo=True)
    Path(__file__).with_name('display_all_stacks.txt' if args.all_threads else 'display_main_stack.txt').write_text(out+err,encoding='utf-8')
    print((out+err)[-7000:])
    if rc:raise RuntimeError('Debugger snapshot failed; inspect process state')
finally:client.close()
