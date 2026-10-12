set -eu
base=/userdata/driving_demo_evidence
prefix=/userdata/detview_shots/shot_det-yolov8n-zebra-merged-v3-rk3568-raw-dfl6-int8_20261005_
sudo -n cp "${prefix}072615.png" "$base/auto_green_072615.png"
sudo -n cp "${prefix}072619.png" "$base/manual_stop_072619.png"
sudo -n cp "${prefix}072624.png" "$base/left_lane_072624.png"
sudo -n cp "${prefix}072628.png" "$base/forced_right_072628.png"
sudo -n cp "${prefix}072634.png" "$base/auto_unknown_072634.png"
sudo -n cp "${prefix}073211.png" "$base/final_073211.png"
sudo -n cp /userdata/linaro/DRIVING_VALIDATION.md "$base/VALIDATION.md"
sudo -n cp /userdata/linaro/detview-driving-demo-src/driving_vision_selftest.log "$base/"
