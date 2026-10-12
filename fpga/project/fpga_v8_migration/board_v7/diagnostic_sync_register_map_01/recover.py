"""Current recovery entry: mapping only, never restart completed compile/synthesis."""
import traceback
import run
from recover_mapping import main
if __name__=='__main__':
    try:main()
    except BaseException:
        run.save('failure.json',{'traceback':traceback.format_exc(),'remote_or_program':False})
        run.save('final_result.json',{'status':'FAIL','tool_or_recovery_failure':True,'traceback':traceback.format_exc(),'remote_or_program':False,'routed':False})
        raise
