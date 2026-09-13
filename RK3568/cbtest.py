import ctypes, os, fcntl, mmap, struct, time
FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
I = lambda n: 0xC0000000 | (4 << 16) | (0x53 << 8) | n
class O(ctypes.Structure):
    _fields_ = [('cur',ctypes.c_uint32),('off',ctypes.c_uint32),('cmd',ctypes.c_uint32),
                ('ddr',ctypes.c_uint32),('ln',ctypes.c_uint32),('rb',ctypes.c_void_p),('wb',ctypes.c_void_p)]
op = O(); op.cmd=0; op.ln=4194304; fcntl.ioctl(FD,I(2),op,True)
op = O(); op.cmd=1; op.ln=4194304; fcntl.ioctl(FD,I(2),op,True)
TX = mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED)
RX = mmap.mmap(FD,4194304,prot=mmap.PROT_READ|mmap.PROT_WRITE,flags=mmap.MAP_SHARED,offset=1048576)
def w(a,v):
    TX[0:4]=struct.pack('<I',v); o=O(); o.off=0; o.ddr=a; o.ln=16; fcntl.ioctl(FD,I(4),o,True)
def ddr(a,n):
    o=O(); o.off=0; o.ddr=a; o.ln=n; fcntl.ioctl(FD,I(5),o,True)
    return bytes(RX[0:n])

A1=0x00800000; A2=0x00A00000
out=[]
w(0x20000080,A1); w(0x200000C0,A2); w(0x20000000,3); w(0x20000040,1)
time.sleep(3)
d1 = ddr(A1, 25600)          # 10 行 (2560B 行距)
time.sleep(3)
d2 = ddr(A1, 25600)          # 3 秒后再抓同时刻同地址
d3 = ddr(A2, 25600)
out.append('== 时域噪声(真实传感器>0, 彩条/静止合成≈0) ==')
ch = sum(1 for x,y in zip(d1,d2) if x != y)
out.append('3秒间变化字节: %d / 25600 (%.1f%%)' % (ch, 100.0*ch/25600))
diff_ab = sum(1 for x,y in zip(d1,d3) if x != y)
out.append('A1 vs A2(相邻两帧) 差异: %d / 25600' % diff_ab)
out.append('== 彩条特征(8条垂直色带) ==')
# 1280 像素/行, 8 条带 = 每带 160 像素 = 320 字节; 列均值轮廓
W = 1280
row = d1[:2560]
col = []
for b in range(8):
    seg = row[b*320:(b+1)*320]
    r=g=bl=n=0
    for i in range(0,320,2):
        px = seg[i] | (seg[i+1]<<8)
        r += (px>>11)&0x1F; g += (px>>5)&0x3F; bl += px&0x1F; n+=1
    col.append((r//n, g//n, bl//n))
out.append('8条带RGB565均值: ' + ' | '.join('(%d,%d,%d)'%c for c in col))
spread = max(max(c) for c in col) - min(min(c) for c in col)
out.append('条带间亮度极差: %d (彩条应>30且各带颜色明显不同)' % spread)
out.append('== 像素统计 ==')
pxs = [(row[i] | (row[i+1]<<8)) for i in range(0,2560,2)]
uniq = {}
for p in pxs: uniq[p] = uniq.get(p,0)+1
top = sorted(uniq.items(), key=lambda kv:-kv[1])[:5]
out.append('首行像素 uniq=%d/1280, top5: %s' % (len(uniq), ', '.join('0x%04X×%d'%(p,c) for p,c in top)))
rs = sum((p>>11)&31 for p in pxs)/len(pxs); gs = sum((p>>5)&63 for p in pxs)/len(pxs); bs = sum(p&31 for p in pxs)/len(pxs)
out.append('RGB565 均值: R=%.1f G=%.1f B=%.1f (彩条会三色均衡/饱和, 暗场应整体低且相近)'%(rs,gs,bs))
open('/tmp/cbtest.out','w').write('\n'.join(out))
