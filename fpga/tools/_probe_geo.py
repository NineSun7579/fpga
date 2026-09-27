import re
b=open(r"source\top.v","rb").read().decode("gbk","replace").splitlines()
print("### ov5640_top param overrides in top.v (cam1 & cam2):")
for i in list(range(1110,1130))+list(range(1212,1228)):
    print("%5d %s"%(i+1,b[i].strip()[:130]))
print()
c=open(r"source\ov5640\ov5640_top.v","rb").read().decode("gbk","replace").splitlines()
print("### ov5640_top.v geometry/param defaults:")
for i,l in enumerate(c):
    if re.search(r"H_CMOS_DISP|V_CMOS_DISP|TOTAL_H|TOTAL_V|total_h_pixel|total_v_pixel|cmos_h_pixel|cmos_v_pixel|PCLK|DATA_WIDTH\s*=|parameter", l) and len(l.strip())<140:
        print("%5d %s"%(i+1,l.strip()[:130]))
