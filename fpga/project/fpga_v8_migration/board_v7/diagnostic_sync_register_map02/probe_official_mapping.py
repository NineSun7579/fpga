"""Read current installed dev_map API only, after the actual comparison."""
from pathlib import Path
import json
import run
H=Path(__file__).resolve().parent;E=H/'evidence'
def main():
    assert (E/'mapping_artifact.json').exists()
    run.wait_queue();run.verify()
    work=E/'official_mapping_api';work.mkdir()
    script=work/'help.tcl'
    script.write_bytes(b'dev_map -help\ndefine_attribute -help\n')
    raw=run.run('mapping_api_help',[run.PDS,'-file',script,'-work_dir',work],work)
    assert b'devmap_remove_dups' in raw and b'devmap_const_prop' in raw and b'devmap_control_set_num' in raw
    run.save('current_mapping_api_review.json',{'pds_executable':str(run.PDS),'executable_sha256':run.sha(run.PDS),'script_sha256':run.sha(script),'actual_help_log_sha256':run.sha(E/'mapping_api_help.log'),'raw_help':raw.decode('ascii','backslashreplace'),'scope':'Current installed command help. No unknown option attempts, no mapping rerun, no PNR.'})
    run.verify()
if __name__=='__main__':main()
