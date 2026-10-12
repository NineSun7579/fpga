from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parent;log=root/'ddr_vendor.log'
r=subprocess.run([r'C:/modeltech64_10.6e/win64/vsim.exe','-c','-do','run_ddr_vendor.do','-l',str(log)],cwd=root,capture_output=True,text=True,encoding='utf-8',errors='replace')
text=log.read_text(encoding='utf-8',errors='replace');print(text[-3200:]);sys.exit(0 if r.returncode==0 and 'CAM34_DDR_VENDOR_PASS' in text and '** Fatal' not in text and '** Error' not in text else 1)
