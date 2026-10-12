# 实际 program session 边界采集

`python -B capture_program_session.py`（或 `--check`）只做本地检查，无输出文件、SSH、device 或 consumer 调用。可加 `--manifest <绝对路径>` 直接调用既有纯离线 delivery verification，不代替其审核。

未来仅在真实 approved delivery、既有 owner preflight 和 vendor/PDS 全部退出且空闲时人工运行：

```text
python -B capture_program_session.py --execute --manifest <delivery原件路径> --owner-preflight <既有preflight原件路径>
```

两个路径必须显式提供，并原样解析为绝对路径传给既有 `new_program_candidate.py --execute`。工具是一次性前台 wrapper，不能加入自动队列或 daemon；不会生成 acceptance/owner 证书，也不执行 reboot/reset/rmmod、BME 修改或额外 DMA/device 操作。

执行前通过既有 `board_host.ssh_connect` 只读获取当前 boot_id、hostname 和 UTC，保留完整 stdout/stderr、退出状态及 helper hash。`program_boot_raw.txt` 仅保存 boot_id 原文，JSON 兼容 `programBootCapture/v1`，另保存本地 UTC 请求区间、monotonic 耗时及同步 uncertainty。远端 date 作为 ISO UTC 解析，绝不推测时区或补造时间线；boot 必须在启动前 60 秒内。

wrapper 在真实子进程启动前和退出后立即记录本地 UTC/monotonic JSONL；`program_session_raw.txt` 保存 validator 所需五个 `key=value`：`started_utc`、`completed_utc`、`receipt_sha256`、`delivery_manifest_sha256`、`exit_code`。成功采集的 `program_session.json` 使用 `programSession/v1` 并绑定 collector、recipe、raw 和 JSONL hash；这仅表示程序边界证据采集完成，不表示 actual board pass。

receipt 必须来自本次 stdout 的唯一结构化 receipt，且与唯一新建 `candidate_run_*` 内原始 receipt 完全一致。禁止按“最近目录”选取；保留原 receipt/log 路径，不复制 frozen runtime、不修改 consumer。退出码 0 但 FAIL、schema 错误、多个 receipt/新增目录、candidate/bit/manifest/preflight hash 漂移均拒绝。失败保存 `program_session_failure.json`、raw 和已记录的真实边界，不生成成功 session。原始日志与后续板级验证仍使用既有 validator。

离线测试：`python -B -m unittest test_capture_program_session -v`。测试仅在临时目录生成假输入，用假子进程和假读取器检查边界、拒绝行为及既有 `program_time_gate` 兼容；不访问 RK、不调用真实 consumer。本次只运行此离线测试。
