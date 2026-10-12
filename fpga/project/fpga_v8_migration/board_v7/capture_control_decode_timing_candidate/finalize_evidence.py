"""Archive exact09 path provenance and audit independently saved evidence."""
from pathlib import Path
import hashlib,json,re

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,text):p.write_text(text,encoding='utf-8')

def main():
    result=json.loads((HERE/'artifacts/results.json').read_text())
    assert result['status']=='PASS' and len(result['runs'])==18
    name='fpga_v8_capture_control_axil_arm_v2.v'
    original=HERE/'original'/name;candidate=HERE/'candidate'/name
    before=json.loads((HERE/'input_hashes.json').read_text())
    assert all(sha(Path(p))==value for p,value in before.items())
    assert original.read_bytes()==Path(next(p for p in before if p.endswith('rtl\\'+name))).read_bytes()
    assert b'wr_offset' not in candidate.read_bytes() and b'addr-LOCAL_BASE' not in candidate.read_bytes()
    path_source=HERE.parent/'physical_subagent_evidence_01/fixed_06/physical_exact_09/evidence/all_reported_failing_paths.json'
    paths=json.loads(path_source.read_text())
    selected=[p for p in paths if p.get('Slack') in (-1.627,-2.086) and 'u_v8_capture_control/aw_addr' in p.get('Startpoint','')]
    assert len(selected)==2
    save(HERE/'exact09_target_paths.json',json.dumps({'source':str(path_source),'source_sha256':sha(path_source),'paths':selected},indent=2)+'\n')
    cycles=sum(int(re.search(r'cycles=(\d+)',r['pass_line'][0])[1]) for r in result['runs'])
    for r in result['runs']:
        log=HERE/'artifacts'/f"{r['base']}_{r['seed']}.log"
        text=log.read_text()
        assert 'DECODE_MITER_PASS' in text and '** Error' not in text and '** Fatal' not in text
    assert 'CAPTURE_ENDPOINT_PASS' in (HERE/'artifacts/integration/modelsim.log').read_text()
    assert 'PASS' in (HERE/'artifacts/integration/comparison.txt').read_text()
    report=f'''# P1 capture control 全地址译码隔离候选

已实际修改并完成 ModelSim SE-64 10.6e 逐周期等价回归。所有改动与工具产物位于本目录；未运行 PDS、remote 或 program。候选没有登记进工程，没有修改 route02/source/frozen/IP/约束或其他代理候选。

## 输入身份与原始时序问题

输入为 `board_v7/source_diagnostics_route_02/rtl/{name}`，原文件按 bytes 复制到 `original/`，没有 GBK→UTF-8 转码；候选通过 ASCII 字节替换生成，非改动字节保持一致。

- 原件 SHA256：`{sha(original)}`。
- 候选 SHA256：`{sha(candidate)}`。
- 原件 SHA 与 `physical_subagent_evidence_01/fixed_06/physical_exact_09/input_hashes.json` 中 `rtl\\{name}` 完全一致。
- 输入控制、四个实际集成依赖、既有测试及 exact09 清单的 SHA 存于 `input_hashes.json`，结束复核结果存于 `input_hashes_after.json`，全部相同。

exact09 原始报告路径已抽取为 `exact09_target_paths.json`（含原报告 SHA 与完整 path detail）：

| 原始 slow setup 路径 | Slack |
| --- | ---: |
| control `aw_addr[8]` → control `s_axil_bresp[1]` | -1.627 ns |
| control `aw_addr[8]` → lease `next_nonzero/.../RS` | -2.086 ns |

两条路径均在 `ddrphy_sysclk`，后一条是同步 RS 数据/控制路径。候选保持 config 请求同拍形成及真实 manager 应答语义，不能将该路径当异步 reset 豁免。

## 实际 RTL 差异与位宽理由

`candidate/{name}` 保持原模块名和端口，独立编译；仿真仅将原件的 module 声明改名为 `_golden`，其余字节保持原样。

1. 三处 `wr_offset==32'hxx` 改为 `aw_addr==(LOCAL_BASE+32'hxx)`。
2. 写 case 改为 `case(aw_addr)`；读 case 改为 `case(addr)`，各标签为 `LOCAL_BASE+32'hxx`。`0x14,0x18` 多标签及原 case 顺序均保留。
3. `PARAM_OK`、`wr_in_range`、`valid_read` 的 overflow/alignment/range 表达式逐字保留，含 33 位上界 `{{1'b0,LOCAL_BASE}}+33'h80`。
4. `wr_offset` 的所有原用途均已转换且无其它用途，才移除其声明。控制、状态机、WSTRB merge、doorbell、key_match、reset 和应答分支未改变。

`LOCAL_BASE` 与每个 `32'hxx` 均明确为 32 位无符号数，case 标签与 32 位地址等宽；合法参数要求对齐且 `LOCAL_BASE<=32'hffffff80`，最大标签为 `ffffff80+7c=fffffffc`，不溢出。非法参数仍由原 `PARAM_OK` 禁止全部读写；非法地址仍由原范围和对齐检查拒绝。无需把 33 位上界检查改成会回绕的 32 位加法。常量加法仅依赖 parameter；源码中的运行时 32 位读写减法已消除。完整差异见 `decode.diff`。

## 黄金与逐周期比较

黄金为实际 route02 原始 RTL，并排实例消费相同输入；没有使用行为镜像作为等价黄金。`sim/compared_signals.json` 列出全部 {len(result['signals_compared'])} 项：所有 AXI/control 输出、全部模块状态寄存器、AW/W holding slots、pending、bound/ack 描述符、计数器，以及 commit/range/doorbell/key_match。上升沿前和 NBA 后、下降沿后均用四态 `!==` 比较，异步 reset 注入另加检查。

定向与随机 miter 共 18 组、{cycles:,} 周期，全部真实 `DECODE_MITER_PASS`：

- 基址 `00000100`、`00000000`、`00000004`、`7fffffc0`、`ffffff7c`、最高合法 `ffffff80`；非法 `ffffff84`、`fffffffc`、未对齐 `00000101`。
- 每组 seed 为 1、202603；每个 seed 4,000 笔定向随机访问，含全 32 位随机、零、ffffffff、高位别名和边界访问。
- 每组穷举 16 个 WSTRB × `BASE-4` 至 `BASE+131` 每字节读写，覆盖全部 32 个字、越界/未对齐、AW 先/W 先/同拍、读写同拍。
- ARM_WAIT、RELEASE_WAIT、延迟真实形态的 accept/reject、accept 与 reject 同拍（reject 优先）、dispatch 同拍 SOF/epoch/config/release 应答；合法参数的 ARM/claim/release/两种等待/矛盾应答均有非零覆盖门槛。
- 中断 ARM_WAIT/RELEASE_WAIT、仅 AW/仅 W 持有槽、B/R 背压时 reset，以及随机非时钟边沿 reset。

## 既有真实控制集成回归

复用 `capture_arm_contract/endpoint` 的 Suite 和 SV 测试，独立复制至 `integration_inputs/`；接入 route02 实际 `fpga_v8_coop_axi128_endpoint`、router、`fpga_v8_capture_lease_tc04` 和 `fpga_v8_coop_control_axil_rfg01`（session_fault 在该正常功能测试中固定为 0）。原控制作为并排 shadow，以同一真实 manager 输入运行，候选输出驱动集成链；输出相等性保证真实 manager 接收到相同请求。原 manager、router、cooperative RTL 没有行为替身。

真实 ModelSim 日志 `artifacts/integration/modelsim.log`：

```text
{result['integration']['pass_line'][0]}
```

499 个操作、26,488 周期、4,288 个既有预期事务/状态事件全部匹配，且逐周期 49 项 RTL 比较通过。覆盖真实 lease 发布/host claim/release、manager 延迟应答与拒绝、ARM dispatch 同拍 SOF 阻断、B/R 快照和背压、reset 中断与双端读写路由。旧测试的 Python 事务 oracle 仅作额外功能回归；等价黄金始终为原 RTL。

## 复现与边界

```powershell
python project/fpga_v8_migration/board_v7/capture_control_decode_timing_candidate/run_regression.py
python project/fpga_v8_migration/board_v7/capture_control_decode_timing_candidate/finalize_evidence.py
```

`--integration-only` 复用已通过的 18 个 miter 日志，仅重跑集成测试。脚本使用目录内 modelsim.ini 与仿真库，不修改全局配置；原始日志、results.json、diff、输入 hash、交付 hash 均独立保存。

本结果为定向/随机周期等价实证，未做形式化全状态证明；本次未综合或布局布线，因此不能宣称 LUT/Fmax/WNS/RS slack 已改善。下一阶段应在另一个授权物理候选中用该模块重新测量上述两条路径。
'''
    save(HERE/'REPORT.md',report)
    result['hashes']={str(p.relative_to(HERE)):sha(p) for p in HERE.rglob('*') if p.is_file() and not any(x.startswith('work') or x=='__pycache__' for x in p.relative_to(HERE).parts) and p.name not in ('results.json','delivery_hashes.json')}
    save(HERE/'artifacts/results.json',json.dumps(result,indent=2)+'\n')
    delivery={k:v for k,v in result['hashes'].items()}
    delivery['artifacts/results.json']=sha(HERE/'artifacts/results.json')
    save(HERE/'delivery_hashes.json',json.dumps(delivery,indent=2)+'\n')
    print(f'DELIVERY_AUDIT_PASS miter_cycles={cycles} integration_cycles=26488 signals=49 input_hashes_unchanged=true')

if __name__=='__main__':main()
