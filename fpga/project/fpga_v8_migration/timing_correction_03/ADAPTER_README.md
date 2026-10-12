# DDR adapter tc03 隔离优化与差分回归

候选：`rtl/fpga_v8_ddr_adapter_tc03.v`，模块名为 `fpga_v8_ddr_adapter_tc03`。
基准：`../whole_candidate_v4_route_01/rtl/fpga_v8_ddr_adapter.v`，直接读取 V4 实际 RTL。
运行：`python project/fpga_v8_migration/timing_correction_03/run_adapter_tests.py`（工作区根目录）。
可通过 `MODELSIM_BIN` 指定 ModelSim；默认 `C:/modeltech64_10.6e/win64`。

## 修改与等价条件

读写两路统一修改组合合法性判定，不增加寄存器或握手延迟。保留 LEN≤15、SIZE=4、BURST=1、16 字节对齐，以及原版参数有效性条件：非零、≤`0x10000000`、16 字节对齐。非法请求仍不接受，并产生原有 sticky error_flags。

16 字节对齐时，原式 `offset+(LEN+1)*16<=4096` 等价于 `addr[11:4]+LEN<=255`。两个 8 位操作数都先扩展到 9 位，最大和为 510；没有低位截断，也没有仅使用 LEN[3:0] 放宽非法请求。

仅当 **实际 32 位参数** `DDR_ADDRESS_LIMIT[11:0]==0` 时，用完整 32 位起始地址 `<DDR_ADDRESS_LIMIT` 替换末地址比较。由于起始地址按 16 字节对齐且突发不能跨 4KB 页，任何起始地址位于上限前的合法突发，其独占末地址均不超过该页对齐上限；反方向由突发至少一拍可得。该化简依赖最终 aw_ok/ar_ok 中的页检查、对齐及合法参数条件。

其他参数保留原版 64 位 `addr+(LEN+1)*16` 和 64 位上限比较，覆盖非 4KB 对齐但有效的 16 字节对齐上限。非 16 字节对齐上限继续拒绝所有请求。零值及超过物理范围的参数也继续拒绝。参数声明维持 `[31:0]`；超过 32 位的覆盖值按原版规则截断，并对截断后的有效值和无效值分别回归。地址接近 `0xffffffff` 时不使用会回绕的 32 位末地址加法。

脚本断言候选的公共接口、全部寄存器状态逻辑、FIFO 接线和 READY 之后的 RTL 与基准字节相同。脚本在编译前扫描模块重名。

## 证据和回归范围

全部新产物位于 `adapter_artifacts/`。`adapter_results.json` 保存源文件和生成产物 SHA-256、参数、测试计数、PASS 标记以及限制。`v4_awlen_full_detail.txt` 是 V4 `all_reported_failing_paths.json` 中该路径 full_detail 的独立摘录。

V4 实际失败路径：`write_arbiter/awlen_reg[5]` → adapter `N6_1_ac1_1` → `N10_1_7...N10_1_28` 进位链 → `N57_9_cpy` → `ov5640_axi_dma_write/len[28]/CE`（V4 RTL 为 `axi_dma_write_tc02.v`）。slack −0.051 ns，17 级逻辑，数据延迟 7.106 ns，其中逻辑 2.624 ns、布线 4.482 ns。候选在默认页对齐上限下使上限比较不再依赖 LEN，4KB 判断只保留 9 位求和。

边界回归包含默认参数下所有 256 个对齐页偏移 × 256 个 LEN，以及各参数下最后合法、刚越界、起始地址等于上限、4KB 末端、地址加法溢出、所有低地址 nibble、SIZE/BURST 枚举和固定种子随机请求。共 15 种参数、266,416 个向量，每个向量检查 AW 和 AR 两路。读写同时检查独立 Python 整数 oracle；非法 VALID 逐拍检查拒绝、无下游请求和原有错误位。合法向量在本阶段作为 READY 组合探针。

事务阶段只在产物目录生成已有 `ddr_adapter_contract` TB 的差分版本，不修改入口。基准与候选共享相同输入；实际未修改的生成 FIFO 各实例独立。所有公共输出使用 `!==` 在上升沿前、上升沿后和下降沿刺激稳定后检查，包含无效周期的数据、状态、FIFO 标志和水位。保留原合同 TB 的满 FIFO、排队、B/R 停顿、ID/WLAST 故障和各阶段复位检查，再加入固定种子 128 组并发随机读写突发及 vendor 停顿。下游采用原合同入口的 DDR 调度 stub。

## 限制

没有运行 PDS、综合、布局布线或新的 STA，故未测量时序改善，不能声称该 −0.051 ns 路径已关闭。有限确定性回归不代替形式等价证明；请求输入是确定的二态值，没有声称 X/Z 输入下组合语义等价。实际 FIFO RTL 已仿真，物理 DDR3 控制器及板级 DDR 未仿真。未修改生产、V4、相机/motion 文件或整机 runner。

ModelSim 正常 `$finish` 在 `-onfinish stop` 下会触发 break；脚本允许正常 break，并另外强制检查 Fatal/Error 文本及完整 PASS 标记。生成 FIFO 的既有未连接水位输出告警不修改 IP 处理。

## RTL SHA-256

- V4 基准：`5b84936d95c74e10bec28734172b49a175e1a17725bc73b3fade9ae089a5e2b8`
- tc03 候选：`f0498521d27b0c0205b2e64a4bb2343fe3023dd0651f1854e2b6ed266baa5a62`

其他只读依赖、脚本和产物的完整哈希见 `adapter_artifacts/adapter_results.json`。

## 本次实测结果

`python run_adapter_tests.py` 完整退出码 0，`adapter_results.json` 状态 PASS。

- 15 组参数、266,416 个边界向量全部通过 AW/AR oracle 和差分检查；29 个公共输出在边界阶段累计 1,066,009 次采样比较。
- 128 组并发随机写突发和读突发全部通过，随机种子 `0x03dd2026`。
- 事务总计 140 次写测试、1,087 个读响应字、12 次非法请求拒绝、16 次共同复位、11,248 个时钟周期；事务阶段结束前随机 PASS 标记处为 33,743 次公共输出采样。
- `VENDOR_ID_FAULT_PASS`、`RANDOM_TRANSACTION_PASS`、`ADAPTER_DIRECTED_PASS`、`ALL_BOUNDARY_PASS` 均存在；无 Error/Fatal。原合同的旧 FIFO 和路由检查也运行完成。
- 公共接口、状态机和 FIFO 接线字节检查通过；运行前后的全部已记录只读依赖哈希相同，运行结束后再次审计相同。
- 已有 FIFO 未接水位端口告警，以及 ModelSim 环境禁用优化告警；重复运行还会有 work 库已存在告警。未修改 IP 或环境以消除这些告警。

结果 JSON SHA-256：`05ca27ddd42cb766e576ae839edd8d33c20565faef511338d1e0726b6e2f2f55`。
