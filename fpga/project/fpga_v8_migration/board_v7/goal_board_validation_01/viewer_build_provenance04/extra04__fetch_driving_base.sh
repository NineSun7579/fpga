set -eu
export GIT_SSH_COMMAND='ssh -o Hostname=ssh.github.com -p 443 -o HostKeyAlias=github.com -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ProxyCommand="python3 /userdata/linaro/github_proxy_connect.py %h %p"'
export http_proxy=http://127.0.0.1:17897
export https_proxy=http://127.0.0.1:17897
repo=/userdata/linaro/projects/fpga
git -C "$repo" fetch origin main --no-tags
git -C "$repo" log -1 --oneline origin/main
git -C "$repo" ls-tree --name-only origin/main RK3568/detview_tdm/driving_demo.h
git -C "$repo" show origin/main:RK3568/detview_tdm/main.cpp > /userdata/linaro/driving_remote_main.cpp
