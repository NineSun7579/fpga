"""Capture the actual X11 desktop and losslessly convert TrueColor XWD to PNG."""
import json,shlex,struct,sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
root=Path(__file__).resolve().parent
out=root/'adopted_flipfb_screenshot';out.mkdir(exist_ok=True)
c=board_ssh.connect()
try:
    remote='/userdata/linaro/ov56401-adopted-flipfb.xwd'
    rc,o,e=board_ssh.run(c,'env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xwd -root -silent -out '+shlex.quote(remote),timeout=20,sudo=True)
    assert rc==0,e
    with c.open_sftp() as s:s.get(remote,str(out/'desktop.xwd'))
    raw=(out/'desktop.xwd').read_bytes();h=struct.unpack('>25I',raw[:100])
    size,version,fmt,depth,w,ht,xoff,order,unit,bitorder,pad,bpp,stride,visual,rm,gm,bm,brgb,entries,colors,*remaining=h
    assert version==7 and fmt==2 and visual in (4,5) and bpp in (16,24,32) and xoff==0
    if visual==5 or bpp==24:
        # Decode DirectColor and its color table using the installed XWD decoder.
        png=remote+'.png'
        rc,o,e=board_ssh.run(c,'ffmpeg -y -i '+shlex.quote(remote)+' -frames:v 1 -update 1 '+shlex.quote(png),timeout=20,sudo=True)
        assert rc==0,e
        with c.open_sftp() as s:s.get(png,str(out/'desktop.png'))
        image=Image.open(out/'desktop.png')
        assert image.size==(w,ht) and w>=1920 and ht>=1080
        image.crop((0,0,1920,1080)).save(out/'hdmi.png')
        (out/'capture.json').write_text(json.dumps({'header':h,'source':'Actual X11 root capture decoded by ffmpeg; not optical capture','hdmi_crop':[0,0,1920,1080]},indent=2))
        print(str(out/'hdmi.png'))
        sys.exit(0)
    pixels=np.ndarray((ht,stride//(bpp//8)),dtype=np.dtype(('<' if order==0 else '>')+('u4' if bpp==32 else 'u2')),buffer=raw,offset=size+colors*12)[:,:w]
    rgb=np.empty((ht,w,3),dtype=np.uint8)
    for i,mask in enumerate((rm,gm,bm)):
        assert mask
        shift=(mask&-mask).bit_length()-1;maximum=mask>>shift
        rgb[:,:,i]=(((pixels&mask)>>shift).astype(np.uint64)*255//maximum).astype(np.uint8)
    image=Image.fromarray(rgb);image.save(out/'desktop.png')
    # The verified HDMI desktop output occupies1920x1080 at0,0.
    assert w>=1920 and ht>=1080
    image.crop((0,0,1920,1080)).save(out/'hdmi.png')
    (out/'capture.json').write_text(json.dumps({'header':h,'source':'X11 root screenshot, not optical capture','hdmi_crop':[0,0,1920,1080]},indent=2))
    print(str(out/'hdmi.png'))
finally:c.close()
