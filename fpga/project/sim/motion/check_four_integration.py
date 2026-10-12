"""Static actual-top wiring checks; vendor IP models are unavailable."""
from pathlib import Path
import re

SOURCE = Path(__file__).resolve().parents[2] / "motion_100h" / "source"


def source(name):
    data = (SOURCE / name).read_bytes()
    return re.sub(rb"//[^\r\n]*|/\*.*?\*/", b"", data, flags=re.S)


def require(condition, message):
    if not condition:
        raise SystemExit("FAIL four-motion integration: " + message)


top = source("top.v")
camera = source("ov5640/ov5640_top.v")
# Instance blocks have parameter lists, followed by a named instance and ports.
instances = re.findall(rb"\bov5640_top\s*#\s*\(.*?\)\s*(\w+)\s*\((.*?)\);", top, re.S)
require(len(instances) == 4, "expected four local ov5640_top instances")
for c in range(1, 5):
    record = f"cam{c}_motion_record".encode()
    require(sum(bool(re.search(rb"\.motion_record\s*\(\s*" + record + rb"\s*\)", ports))
                for _, ports in instances) == 1, f"CAM{c} positive motion port wiring")
require(len(re.findall(rb"\bmotion_stream_adapter\s*#", camera)) == 1,
        "one motion adapter per local camera instance")
require(re.search(rb"\.pixel_rgb565\s*\(kf_video_data\).*?\.pixel_valid\s*\(kf_video_valid\).*?"
                  rb"\.vsync\s*\(kf_video_vsync\).*?\.motion_record\s*\(motion_record\)", camera, re.S),
        "local adapter taps the actual KF stream")
require(not re.search(rb"\bmotion_stream_adapter\s*(?:#|\w+\s*\()", top),
        "no additional direct top motion adapter")
for c in (5, 6):
    require(re.search(fr"wire\s*\[319:0\]\s*cam{c}_motion_record\s*=\s*320'b0\s*;".encode(), top),
            f"unused CAM{c} motion record zero")
    require(re.search(fr"\bov5640_ddr\s*#\s*\(.*?\)\s*cam{c}_ov5640_ddr\s*\(".encode(), top, re.S),
            f"CAM{c} video DDR engine preserved")
    require(re.search(fr"\baxi_dma_write\s*#\s*\(.*?\)\s*cam{c}_axi_dma_write\s*\(".encode(), top, re.S),
            f"CAM{c} video DMA preserved")
    for port in ("s_data", "s_data_valid", "s_vsync"):
        signal = {"s_data": "pix", "s_data_valid": "de", "s_vsync": "vs"}[port]
        require(re.search(fr"\.{port}\s*\(\s*cam{c}_{signal}\s*\)".encode(), top),
                f"CAM{c} positive video {port} wiring")
require(re.search(rb"motion_records\s*=\s*\{\s*cam6_motion_record\s*,\s*cam5_motion_record\s*,\s*"
                  rb"cam4_motion_record\s*,\s*cam3_motion_record\s*,\s*cam2_motion_record\s*,\s*cam1_motion_record\s*\}", top),
        "six-slot ABI order")
print("PASS four-motion static actual-top integration: four local instances/adapters and CAM1-4 records; "
      "CAM5/6 zero records with video DDR/DMA preserved; six-slot ABI order. Full vendor top was not simulated.")
