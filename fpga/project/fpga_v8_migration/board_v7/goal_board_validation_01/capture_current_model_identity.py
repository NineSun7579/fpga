"""Read-only privileged model hashes; never launch viewer or access DMA."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'tools'))
from board_host import ssh_connect,board_host
command='sudo -n sha256sum /root/npu/trafficlight/det-yolov8n-trafficlight-16cls-640x480-rk3568-raw-dfl6-int8.rknn /root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn'
client=ssh_connect()
try:
    _,out,err=client.exec_command(command,timeout=30)
    result={'host':board_host(),'captured_utc':datetime.now(timezone.utc).isoformat(),
            'command':command,'stdout':out.read().decode(),'stderr':err.read().decode(),
            'exit_code':out.channel.recv_exit_status(),'device_operations':False}
finally:client.close()
(HERE/'current_model_identity03.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
