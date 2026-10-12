from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
def pins(names):return '[get_pins {'+' '.join(sorted(set(names)))+'}]'
def main():
    c=json.loads((HERE/'classification.json').read_bytes())
    ordinary=c['ordinary_pairs']
    commands={
      'ordinary':'report_timing -report_exception TRUE -from '+pins(r['launch_CLK'] for r in ordinary)+' -to '+pins(r['capture_D'] for r in ordinary)+' -max_path 2000 -nworst 10',
      'negedge':'report_timing -report_exception TRUE -from '+pins(r['cell']+'/CLK' for r in c['negedge'])+' -to [get_clocks {cmos1_pclk cmos2_pclk cmos3_pclk cmos4_pclk}] -max_path 2000 -nworst 10',
      'reset':'report_timing -report_exception TRUE -to '+pins(r['cell']+'/P' for r in c['all_classified_registers'].values() if r['classification']=='reset_chain' and 'P' in r['pins'])+' -max_path 2000 -nworst 10',
    }
    for name,cmd in commands.items():(HERE/(name+'_report_command.txt')).write_text(cmd)
    print('prepared',list(commands),'ordinary pairs',len(ordinary),'negedge starts',len(c['negedge']))
if __name__=='__main__':main()
