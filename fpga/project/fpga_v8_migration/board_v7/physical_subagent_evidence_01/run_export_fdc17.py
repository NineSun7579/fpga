"""Read mapped constraints through official export_fdc on an isolated project copy."""
from pathlib import Path
import shutil,re
from native_query08 import BASE,idle,run
def main():
    idle()
    source=BASE/'fixed_06/stage_map13'
    work=BASE/'fixed_06/stage_export17_work'
    shutil.copytree(source,work)
    project=work/'stage_map13.pds'
    raw=project.read_bytes()
    def absolute(m):return b'(_file "'+(work/m.group(1).decode('ascii')).resolve().as_posix().encode('ascii')+b'"'
    raw=re.sub(rb'\(_file "([^"\r\n]+)"',absolute,raw);project.write_bytes(raw)
    text='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nopen_project {'+project.as_posix()+'}\nexport_fdc -file {'+(work/'actual_export.fdc').as_posix()+'} -no_log FALSE\n'
    run('stage_export17',text,[source/'device_map/v7_sdt_top_map.adf'])
if __name__=='__main__':main()
