[UNDER AGENTS]

# PDS 外部设计实现与仿真指南

适用于：

```text
Pango Design Suite 2022.2-SP6.4
E:\pango\PDS_2022.2-SP6.4
Windows + PowerShell
ModelSim 或 QuestaSim
```

PDS 负责从 HDL 到综合、布局布线和位流生成；仿真由外部 ModelSim/QuestaSim 执行。

## 1. 推荐工程结构

```text
demo/
├─ rtl/                    # RTL 源码
│  ├─ top.sv
│  └─ include/
├─ ip/                     # PDS IP Compiler 生成文件
├─ tb/
│  └─ tb_top.sv
├─ constraints/
│  └─ top.fdc
├─ scripts/
│  ├─ build.tcl
│  ├─ compile_simlib.tcl
│  ├─ run_behav.do
│  ├─ run_post_syn.do
│  ├─ run_post_pnr_func.do
│  ├─ run_post_pnr_timing.do
│  └─ run.ps1
├─ sim/
│  ├─ rtl.f
│  └─ tb.f
└─ build/                  # 全部生成物，不提交版本库
   ├─ pds/
   ├─ simlib/
   ├─ sim/
   └─ logs/
```

Tcl、DO 和 `.f` 文件中的 Windows 路径建议统一使用 `/`。

## 2. 检查环境

```powershell
$PdsBin = 'E:\pango\PDS_2022.2-SP6.4\bin'
$QuestaBin = 'C:\questasim64\win64'   # 按实际安装路径修改

& "$PdsBin\pds_shell.exe" -version
& "$QuestaBin\vsim.exe" -version
& "$QuestaBin\vlog.exe" -version
```

预期 PDS 输出：

```text
2022.2-SP6.4
```

本机当前没有找到 `vsim.exe`，因此必须先安装 ModelSim/QuestaSim。

## 3. 编译 Pango 仿真库

创建 `scripts/compile_simlib.tcl`：

```tcl
# Pango 仿真库只需在 PDS、仿真器版本或器件系列变化后重新编译。

set project_root [file normalize "[file dirname [info script]]/.."]
set simlib_dir   "$project_root/build/simlib"

file mkdir $simlib_dir

puts "INFO: compiling Pango simulation libraries into $simlib_dir"

compile_simlib \
    -Simulator {QuestaSim Simulator} \
    -family {Logos2} \
    -language {Verilog} \
    -library {BOTH} \
    -simulator_exec_path {C:/questasim64/win64} \
    -directory $simlib_dir

puts "INFO: simulation library compilation completed"
```

可选值：

- 仿真器：`ModelSim Simulator`、`QuestaSim Simulator`
- 仿真库：`USIM`、`VSIM`、`BOTH`
- 器件系列：例如 `Logos`、`Logos2`、`Titan`、`Titan2`

其中：

- `USIM`：行为级和综合后仿真；
- `VSIM`：PNR 后功能及时序仿真；
- 一般直接选择 `BOTH`。

执行：

```powershell
$PdsShell = 'E:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe'

& $PdsShell `
  -file "$PWD/scripts/compile_simlib.tcl" `
  -work_dir "$PWD/build/pds-simlib" `
  -project_name simlib
```

检查：

```powershell
Test-Path '.\build\simlib\usim'
Test-Path '.\build\simlib\vsim'
```

仓库提供参数化入口，可在不改工程源清单的情况下覆盖仿真器路径、库类型和器件系列：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\compile_simlib.ps1 `
  -SimulatorExecPath 'C:\questasim64\win64' `
  -Library BOTH `
  -Family Logos2
```

入口会先检查 `vsim.exe`、`vlog.exe` 和 `vlib.exe`，再调用 PDS；任一文件缺失即返回非零，不会生成“编译完成”的假日志。

## 4. PDS 设计实现脚本

创建 `scripts/build.tcl`：

```tcl
# PDS 2022.2-SP6.4 命令行实现流程。

set project_root [file normalize "[file dirname [info script]]/.."]

set rtl_dir        "$project_root/rtl"
set ip_dir         "$project_root/ip"
set constraint_dir "$project_root/constraints"

puts "INFO: project root is $project_root"

# 必须替换为实际器件信息。
set_arch \
    -family Logos2 \
    -device PG2L100H \
    -package FBG676 \
    -speedgrade -6

# RTL 文件。PDS 根据扩展名识别文件类型。
add_design "$rtl_dir/top.sv"

# 其他 RTL/IP 生成文件逐个添加。
# add_design "$rtl_dir/module_a.sv"
# add_design "$ip_dir/pll/pll.v"
# add_design "$ip_dir/pll/pll.idf"

# 添加 FDC/SDC/PCF 等约束。
add_constraint "$constraint_dir/top.fdc"

puts "INFO: compiling RTL"

compile \
    -top_module top \
    -system_verilog \
    -include_path [list "$rtl_dir/include"]

puts "INFO: running ADS synthesis"

synthesize \
    -ads \
    -top_module top \
    -system_verilog \
    -frequency 100 \
    -max_parallel_jobs 4 \
    -write_verilog TRUE

puts "INFO: mapping design"

dev_map \
    -top_module top \
    -detail

puts "INFO: running place and route"

pnr \
    -optimize_multi_corner_timing \
    -fix_hold_violation \
    -number_of_router_thread 4 \
    -report_timing

puts "INFO: generating timing report"

report_timing \
    -nworst 10 \
    -max_path 100 \
    -report_exception TRUE

puts "INFO: generating post-PNR simulation netlist and SDF"

gen_netlist \
    -sdf_annotate TRUE \
    -process_corner slow

puts "INFO: generating bitstream"

gen_bit_stream \
    -create_bit_file TRUE \
    -create_bin_file

puts "INFO: PDS implementation completed"
```

首次使用时必须修改：

```tcl
set_arch ...
-top_module top
-frequency 100
```

器件的 family、device、package、speedgrade 必须和板卡芯片完全一致。

## 5. 从 PowerShell 执行实现

创建 `scripts/run.ps1`：

```powershell
param(
    [ValidateSet('compile', 'synthesize', 'dev_map', 'pnr',
        'report_timing', 'gen_netlist', 'gen_bit_stream')]
    [string]$RunTo = 'gen_bit_stream'
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PdsShell = 'E:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe'
$BuildDir = Join-Path $ProjectRoot 'build\pds'
$LogDir = Join-Path $ProjectRoot 'build\logs'
$BuildScript = Join-Path $PSScriptRoot 'build.tcl'
$LogFile = Join-Path $LogDir "pds-$RunTo.log"

New-Item -ItemType Directory -Force -Path $BuildDir, $LogDir |
    Out-Null

Write-Host "INFO: running PDS to stage '$RunTo'"

# build.tcl 已经显式执行全部阶段，因此通常不需要 -run。
& $PdsShell `
  -file $BuildScript `
  -work_dir $BuildDir `
  -project_name top `
  2>&1 | Tee-Object -FilePath $LogFile

$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0) {
    throw "PDS failed with exit code $ExitCode. See $LogFile"
}

Write-Host "INFO: PDS completed successfully"
```

运行完整流程：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

如果已经有 `.pds` 工程，也可以直接运行到指定阶段：

```powershell
& 'E:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe' `
  -project 'D:\demo\build\pds\top.pds' `
  -run gen_bit_stream
```

## 6. 行为级仿真

创建 `sim/rtl.f`：

```text
+incdir+rtl/include
rtl/top.sv
```

创建 `sim/tb.f`：

```text
tb/tb_top.sv
```

创建 `scripts/run_behav.do`：

```tcl
# 必须从工程根目录启动本脚本。
onerror {
    puts "ERROR: behavior simulation failed"
    quit -code 1 -force
}

file mkdir build/sim/behav
file mkdir build/logs

transcript file build/logs/sim-behav.log

vlib build/sim/behav/work
vmap work build/sim/behav/work

# Pango PNR 前仿真库。
vmap usim build/simlib/usim

vlog -sv -work work -f sim/rtl.f
vlog -sv -work work -f sim/tb.f

# GTP_GRS 是部分 Pango 原语需要的全局复位模型。
vsim \
    -voptargs="+acc" \
    -L usim \
    work.tb_top \
    usim.GTP_GRS

run -all

puts "INFO: behavior simulation completed"
quit -code 0 -force
```

执行：

```powershell
& 'C:\questasim64\win64\vsim.exe' `
  -c `
  -do 'do scripts/run_behav.do'
```

Testbench 应当自检，不能只观察波形：

```systemverilog
initial begin
    // 避免测试永久挂起。
    #1ms;
    $fatal(1, "Simulation timeout");
end

initial begin
    // 测试流程……
    wait (test_finished);

    if (error_count != 0) begin
        $fatal(1, "Test failed: %0d errors", error_count);
    end

    $display("TEST PASS");
    $finish;
end
```

这样 CI 可以根据 `vsim.exe` 的退出码判断测试结果。

## 7. 综合后仿真

ADS 综合时启用：

```tcl
synthesize -ads -write_verilog TRUE
```

PDS 会生成综合后 `.vm` 或 Verilog 网表。将实际文件路径写入 `run_post_syn.do`：

```tcl
onerror {quit -code 1 -force}

file mkdir build/sim/post_syn
file mkdir build/logs
transcript file build/logs/sim-post-syn.log

vlib build/sim/post_syn/work
vmap work build/sim/post_syn/work
vmap usim build/simlib/usim

# 替换成 PDS 实际生成的综合网表。
vlog -work work build/pds/path/to/top.vm
vlog -sv -work work -f sim/tb.f

vsim \
    -voptargs="+acc" \
    -L usim \
    work.tb_top \
    usim.GTP_GRS

run -all
quit -code 0 -force
```

运行：

```powershell
& 'C:\questasim64\win64\vsim.exe' `
  -c `
  -do 'do scripts/run_post_syn.do'
```

## 8. PNR 后功能仿真

先在 PDS 执行：

```tcl
gen_netlist -func_sim_only
```

然后创建 `scripts/run_post_pnr_func.do`：

```tcl
onerror {quit -code 1 -force}

file mkdir build/sim/post_pnr_func
file mkdir build/logs
transcript file build/logs/sim-post-pnr-func.log

vlib build/sim/post_pnr_func/work
vmap work build/sim/post_pnr_func/work
vmap usim build/simlib/usim
vmap vsim build/simlib/vsim

# 替换成 PDS 实际生成的 PNR 后功能网表。
vlog -work work build/pds/path/to/top_sim.v
vlog -sv -work work -f sim/tb.f

vsim \
    -voptargs="+acc" \
    -L usim \
    -L vsim \
    work.tb_top \
    usim.GTP_GRS

run -all
quit -code 0 -force
```

## 9. PNR 后时序仿真

PDS 生成带 SDF 的网表：

```tcl
gen_netlist \
    -sdf_annotate TRUE \
    -process_corner slow
```

创建 `scripts/run_post_pnr_timing.do`：

```tcl
onerror {quit -code 1 -force}

file mkdir build/sim/post_pnr_timing
file mkdir build/logs
transcript file build/logs/sim-post-pnr-timing.log

vlib build/sim/post_pnr_timing/work
vmap work build/sim/post_pnr_timing/work
vmap usim build/simlib/usim
vmap vsim build/simlib/vsim

vlog -work work build/pds/path/to/top_sim.v
vlog -sv -work work -f sim/tb.f

# /tb_top/dut 必须是 testbench 中 DUT 的真实层级。
vsim \
    -voptargs="+acc" \
    -L usim \
    -L vsim \
    -sdfmax /tb_top/dut=build/pds/path/to/top.sdf \
    work.tb_top \
    usim.GTP_GRS

run -all
quit -code 0 -force
```

需要重点检查日志中是否出现：

```text
SDF annotation error
Failed to find instance
Timing check violation
Negative timing check
```

如果 SDF 实例层级不匹配，时序仿真即使启动成功也没有意义。

## 10. 推荐执行顺序

```text
编译仿真库（首次）
       │
       ├─ 行为级仿真
       │
       └─ PDS 实现
            ├─ compile
            ├─ synthesize
            ├─ 综合后仿真
            ├─ dev_map
            ├─ pnr
            ├─ report_timing
            ├─ gen_netlist
            ├─ PNR 后功能仿真
            ├─ PNR 后时序仿真
            └─ gen_bit_stream
```

建议 CI Gate：

1. 行为级仿真必须通过。
2. PDS 进程退出码必须为 0。
3. 时序报告必须满足约束，不能只判断 `report_timing` 命令成功。
4. PNR 后时序仿真必须成功加载 SDF。
5. Testbench 必须输出明确的 `TEST PASS`。
6. 最终确认 `.bit`/`.bin` 文件存在且大小非零。

仓库级静态一致性检查（不启动 PDS 或外部仿真器）：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\check_repo_consistency.ps1
```

该检查确认三个项目的 README、`build.tcl`、`run.ps1`、`check_build.ps1`、顶层声明、七阶段入口、版本记录和 `build/` 忽略状态；它不能替代项目级 PDS gate、STA 或四级仿真。

## 11. 常见问题

- `License checkout failed`：检查 PDS License 是否有效。
- `vsim.exe not found`：`-simulator_exec_path` 必须指向包含 `vsim.exe` 的目录。
- `Library usim/vsim not found`：先执行 `compile_simlib`。
- `Unknown module GTP_*`：遗漏 USIM，或者 Pango IP 生成文件没有加入。
- `Unknown module V_*`：遗漏 VSIM。
- 综合成功但 PNR 失败：优先检查器件型号、IO 管脚和时钟约束。
- 仿真一直不退出：testbench 缺少超时和 `$finish`。
- SDF 无法标注：`/tb_top/dut` 层级与实际 DUT 实例名不一致。
- Tcl 路径解析异常：把 `\` 改为 `/`。
- `simulate` 无法识别：`simulate` 不是 2022.2-SP6.4 的 `pds_shell` Tcl 命令；应直接调用 `vsim.exe`。

本机参考手册：

- `E:\pango\PDS_2022.2-SP6.4\doc\Pango_Design_Suite_User_Guide.pdf`
- `E:\pango\PDS_2022.2-SP6.4\doc\Simulation_User_Guide.pdf`

版本提醒：2026 年 8 月 29 日核对官方软件下载页时，公开列出的 Win64 版本为 `PDS_2024.2-SP2-EN-ads-win64`，上传日期为 2026 年 3 月 23 日。本仓库的可重复构建与签核基线仍固定为本机 `2022.2-SP6.4`；验证其他版本时必须侧装并使用独立 `build/`，不得覆盖现有环境或混用生成物。
