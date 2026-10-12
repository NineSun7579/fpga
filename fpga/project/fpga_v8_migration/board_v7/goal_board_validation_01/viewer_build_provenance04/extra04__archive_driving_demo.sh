set -eu
export GIT_SSH_COMMAND='ssh -o Hostname=ssh.github.com -p 443 -o HostKeyAlias=github.com -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ProxyCommand="python3 /userdata/linaro/github_proxy_connect.py %h %p"'
export http_proxy=http://127.0.0.1:17897
export https_proxy=http://127.0.0.1:17897
repo=/userdata/linaro/projects/fpga
work=/userdata/linaro/driving-demo-archive-worktree
branch=feat/hdmi-driving-demo-20261005
source=/userdata/linaro/detview-driving-demo-src
git -C "$repo" worktree add --no-checkout -b "$branch" "$work" origin/main
git -C "$work" sparse-checkout set --no-cone '/RK3568/detview_tdm/'
git -C "$work" read-tree -mu HEAD
target=$work/RK3568/detview_tdm
for file in vision_types.h vision_pipeline.h vision_pipeline.cpp template_tracker.h template_tracker.cpp \
            calibration_capture.h calibration_capture.cpp camera_dma.h frame_metrics.h display_perf.h; do
    cmp "$source/$file" "$target/$file"
done
cp "$source/main.cpp" "$source/detview.pro" "$source"/driving*.cpp "$source"/driving*.h "$target/"
cp "$source/inference_geometry.h" "$source/inference_geometry_selftest.cpp" "$target/"
cp "$source/hdmi_view.h" "$source/hdmi_view_selftest.cpp" "$source/rknn_api.h" "$target/"
sed -i 's/[[:blank:]\r]*$//' "$target/detview.pro" "$target/rknn_api.h"
git -C "$work" add -- RK3568/detview_tdm
git -C "$work" diff --cached --check
git -C "$work" commit -m 'rk3568: simulate intersection driving from HDMI signal detections'
push_batch() {
    for attempt in 1 2 3; do
        if git -C "$work" push -u origin "HEAD:refs/heads/$branch"; then return 0; fi
        sleep 2
    done
    return 1
}
push_batch
echo DRIVING_SOURCE_PUSHED
cp "$source/DRIVING_DEMO.md" "$source/TRAFFICLIGHT_SUPPORT.md" "$target/"
python3 - "$target" <<'PY'
import pathlib, sys
target = pathlib.Path(sys.argv[1])
readme = target / 'README.md'
text = readme.read_text()
note = '十字路口 HDMI 智能驾驶模拟：`./detview --driving-demo --fullscreen`。方向键选车道，`A` 自动、`X` 停车、`B` 强制行驶。使用与判定规则见 [驾驶模拟](DRIVING_DEMO.md)。\n\n'
text = text.replace('## 使用\n\n', '## 使用\n\n' + note, 1)
readme.write_text(text)
support = target / 'TRAFFICLIGHT_SUPPORT.md'
text = support.read_text().replace('This source change does not modify any active binary or runtime deployment.',
    'This decoder is included in the deployed driving demo. See evidence/driving_demo_20261005/VALIDATION.md for native build and runtime verification.')
support.write_text(text)
PY
git -C "$work" add -- RK3568/detview_tdm/DRIVING_DEMO.md RK3568/detview_tdm/TRAFFICLIGHT_SUPPORT.md RK3568/detview_tdm/README.md
git -C "$work" commit -m 'docs: explain driving simulator controls and model geometry'
push_batch
echo DRIVING_DOCS_PUSHED
mkdir -p "$target/evidence/driving_demo_20261005"
sudo -n cp /userdata/driving_demo_evidence/VALIDATION.md /userdata/driving_demo_evidence/*selftest.log "$target/evidence/driving_demo_20261005/"
sudo -n cp /userdata/driving_demo_evidence/*.png "$target/evidence/driving_demo_20261005/"
sudo -n cp /userdata/driving_demo_evidence/driving_state_events.log "$target/evidence/driving_demo_20261005/"
git -C "$work" add -f -- RK3568/detview_tdm/evidence/driving_demo_20261005
git -C "$work" commit -m 'rk3568: archive driving simulator checks and HDMI screenshots'
push_batch
echo DRIVING_EVIDENCE_PUSHED
git -C "$work" log -3 --oneline
git -C "$work" ls-remote origin "refs/heads/$branch"
