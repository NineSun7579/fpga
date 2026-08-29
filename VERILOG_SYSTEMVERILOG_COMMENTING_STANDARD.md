# Verilog/SystemVerilog RTL 注释与设计文档规范

| 字段 | 值 |
|---|---|
| 规范名称 | Verilog/SystemVerilog RTL 注释与设计文档规范 |
| 英文名称 | Verilog/SystemVerilog RTL Commenting and Design Documentation Standard |
| 规范标识 | VSCS |
| 版本 | 1.0.0 |
| 状态 | Draft |
| 发布日期 | 2026-08-29 |
| 文档语言 | 简体中文 |
| 默认编码 | UTF-8 |
| 语言基线 | IEEE 1800-2023；兼容 Verilog-2001 项目 |
| 适用对象 | 可综合 RTL 及其直接配套的约束、验证和设计文档 |
| 文档许可 | 未指定；由所在仓库的独立许可文件决定 |
| 维护者 | 由采用本规范的项目或组织指定 |

## 摘要

本规范定义 Verilog/SystemVerilog RTL 中应记录的设计意图、接口契约、假设、不变量、延迟、故障模式及修改风险，并规定 FSM、复位、CDC/RDC 和 Doxygen 集成的最低文档要求。

本规范的核心原则是：

> 注释负责解释代码无法可靠表达的设计事实；代码、约束和自动化工具负责可机械推导或验证的事实。

注释不得替代编译、lint、仿真、形式验证、CDC/RDC、综合或静态时序分析。

## 文档状态与非法律声明

**VSCS-META-001 — MUST**  
本文档必须被视为工程规范，而不是软件许可证、法律合同、安全认证或产品质量保证。

**VSCS-META-002 — MUST**  
采用者必须通过独立的许可证或协议处理 RTL、约束、脚本、示例及本文档本身的版权和其他权利。

**VSCS-META-003 — MUST**  
本规范与适用法律、项目安全要求、目标器件要求或经批准的签核规则冲突时，项目必须记录冲突，并执行约束更严格的一方。

---

## 1. 适用范围

本规范适用于：

- 可综合 Verilog-2001 和 SystemVerilog RTL；
- package、interface、module、parameter、port、signal 和 process 的注释；
- FSM、复位、CDC 与 RDC 的设计说明；
- 与 RTL 直接相关的 Doxygen 或其他生成文档；
- Code Review 和发布签核中的注释合规检查。

本规范不定义：

- 完整的 RTL 命名、排版或目录规范；
- 某一厂商独占的综合、布局或约束语法；
- 功能安全认证流程；
- 软件或硬件知识产权许可证；
- 用注释代替 assertion、约束、测试或工具报告的方法。

**VSCS-SCOPE-001 — MUST**  
项目必须明确合规对象是文件、模块、IP、仓库还是发布版本。

**VSCS-SCOPE-002 — SHOULD**  
项目应将本规范与独立的 RTL 编码规范、验证规范和签核清单配套使用。

---

## 2. 规范性语言

本文档中的 `MUST`、`MUST NOT`、`SHOULD`、`SHOULD NOT` 和 `MAY` 按 BCP 14（RFC 2119 与 RFC 8174）解释，并且只有以英文大写形式出现时才具有规范性含义。

- `MUST / MUST NOT`：绝对要求或绝对禁止。
- `SHOULD / SHOULD NOT`：通常应遵守；偏离前必须理解并权衡后果。
- `MAY`：可选行为。

**VSCS-KEY-001 — MUST**  
每项可独立验证的要求必须使用唯一编号，格式为 `VSCS-<AREA>-NNN`。

**VSCS-KEY-002 — MUST NOT**  
已发布的要求编号不得被重新分配给不同语义。

除非明确标为“资料性”，本规范中带编号的条款均为规范性内容。示例、说明和附录默认属于资料性内容，不得单独建立额外义务。

---

## 3. 术语

### 3.1 设计意图（Design Intent）

说明设计为何存在、解决什么问题，以及为何采用当前实现方式。

### 3.2 接口契约（Interface Contract）

模块与外部环境之间可观察的约定，包括信号语义、有效电平、时序关系、单位、范围、延迟、吞吐率、背压和错误行为。

### 3.3 假设（Assumption）

设计正确工作所依赖、但不由该设计自身保证的外部条件。

### 3.4 不变量（Invariant）

在规定工作条件下始终应成立的性质。

### 3.5 风险（Hazard）

在特定参数、输入、时钟、复位、跨域或工具处理条件下可能导致错误的非显然因素。

### 3.6 机器可验证事实（Machine-verifiable Fact）

能够由源码解析、elaboration、lint、CDC/RDC、综合、STA、测试或版本控制系统可靠获得的事实。

### 3.7 CDC 与 RDC

- CDC：Clock Domain Crossing，时钟域交叉。
- RDC：Reset Domain Crossing，复位域交叉。

### 3.8 偏离（Deviation）

在明确范围内不遵守一项 `MUST` 或 `MUST NOT` 要求的已批准例外。

---

## 4. 合规模型

合规状态分为：

| 状态 | 含义 |
|---|---|
| `Compliant` | 满足全部适用的强制要求 |
| `Compliant with Approved Deviations` | 未满足项均有有效且已批准的偏离 |
| `Non-compliant` | 存在未满足且未经批准的强制要求 |

**VSCS-CONF-001 — MUST**  
一个对象只有满足所有适用的 `MUST` 和 `MUST NOT` 要求，或对全部未满足项持有有效偏离记录时，才可以声明符合本规范。

**VSCS-CONF-002 — MUST**  
注释与实现、约束或验证结果不一致时，该不一致必须作为缺陷处理；相关对象不得声明为 `Compliant`。

**VSCS-CONF-003 — SHOULD NOT**  
注释不应重复维护可以由代码或工具稳定推导的信息。

**VSCS-CONF-004 — MAY**  
不适用于某对象的条款可以标记为 `N/A`，但必须能由该条款的适用条件直接证明，而不能以 `N/A` 规避检查。

建议的合规声明：

```text
Conforms-To: VSCS 1.0.0
Conformance-Target: Module
Status: Compliant
Deviations: None
```

---

## 5. 事实来源与通用原则

| 信息 | 首选事实来源 |
|---|---|
| 参数名、类型、默认值、端口方向 | RTL 声明 |
| 驱动者、读取者、敏感性、多驱动 | parser、elaboration、lint |
| latch、位宽、截断、case 覆盖 | lint |
| FSM 实际编码、资源推断、工具属性 | 综合报告 |
| CDC/RDC 结构及重汇聚 | CDC/RDC 报告 |
| 时钟频率和时序例外 | SDC/XDC/FDC 等约束与 STA |
| 资源数量和关键路径 | 对应器件与配置的综合/实现报告 |
| 作者、日期、CR 和修改历史 | Git 与工单系统 |
| 设计意图、假设、不变量和风险 | 注释、规格、assertion |
| 示例正确性 | CI 编译、elaboration 或测试 |

**VSCS-GEN-001 — MUST**  
注释必须优先记录无法从 RTL 语法可靠推导的设计信息，包括设计意图、接口契约、外部假设、不变量、延迟、吞吐率、单位、编码、故障模式及修改风险。

**VSCS-GEN-002 — MUST NOT**  
注释不得把未经验证的推断写成“安全”“无毛刺”“不会丢失”“消除亚稳态”等绝对保证。

**VSCS-GEN-003 — MUST**  
实现变化导致注释不再准确时，同一变更必须更新或删除相关注释。

**VSCS-GEN-004 — SHOULD NOT**  
注释不应逐句翻译代码，也不应手工镜像完整 `reads`、`drives`、端口或状态转移清单。

**VSCS-GEN-005 — MUST**  
源文件必须使用 UTF-8 编码。

**VSCS-GEN-006 — SHOULD**  
描述性内容应采用团队统一语言；标准术语、信号名、需求编号和工具属性应保留原始英文拼写。

**VSCS-GEN-007 — SHOULD**  
注释应尽可能靠近其约束的代码。影响多个模块的系统级约束应放入架构或接口文档，并从源码注释指向该事实源。

**VSCS-GEN-008 — MUST NOT**  
不得用“无”“N/A”或重复代码语义来填充不适用的模板字段；不适用字段必须删除。

---

## 6. 文件、模块、参数与接口

### 6.1 文件级文档

**VSCS-FILE-001 — MUST**  
承担独立设计职责的 RTL 文件必须说明其用途、职责边界和最重要的外部约束。

**VSCS-FILE-002 — MUST NOT**  
RTL 文件不得手工维护作者、最后修改日期、文件版本或 Revision History；这些信息由 Git 和发布记录管理。

**VSCS-FILE-003 — MAY**  
项目可以按组织政策使用 SPDX 标识，但不得自行编造或推断许可证。

### 6.2 模块与接口契约

**VSCS-MOD-001 — MUST**  
模块文档必须说明模块职责，以及不属于该模块职责的边界。

**VSCS-MOD-002 — MUST**  
参数存在非显然单位、合法范围、边界包含关系或非法值行为时，文档必须说明这些内容。

**VSCS-MOD-003 — MUST**  
关键参数约束必须尽可能通过 elaboration check、assertion、类型或生成条件执行；不得只写在注释里。

**VSCS-MOD-004 — MUST**  
端口存在非显然极性、采样边沿、有效周期、保持规则、延迟、背压或错误语义时，接口契约必须明确说明。

**VSCS-MOD-005 — SHOULD NOT**  
接口文档不应重复端口方向、位宽和参数默认值，除非生成工具无法从 RTL 获取且该重复信息由 CI 校验。

**VSCS-MOD-006 — MUST**  
实例化示例若被声明为“可直接使用”，必须由 CI 编译或 elaboration；未经检查的片段只能标为资料性伪代码。

### 6.3 信号与局部声明

**VSCS-SIG-001 — SHOULD**  
信号注释应说明非显然的物理含义、单位、编码、所属时钟域、生命周期或协议角色。

**VSCS-SIG-002 — SHOULD NOT**  
信号名已经清楚表达含义时，不应添加“`count` 是计数器”之类的低信息注释。

---

## 7. 时序与组合过程

### 7.1 SystemVerilog 过程语义

**VSCS-PROC-001 — MUST**  
SystemVerilog 中的触发器逻辑必须使用 `always_ff`，组合逻辑必须使用 `always_comb`；有意推断锁存器时才可使用 `always_latch`。工具不支持时必须记录偏离。

**VSCS-PROC-002 — MUST**  
时序状态更新必须使用非阻塞赋值 `<=`；组合赋值必须使用阻塞赋值 `=`。

**VSCS-PROC-003 — MUST**  
`always_comb` 的输出必须在所有执行路径赋值，通常应在块首设置默认值。

**VSCS-PROC-004 — MUST NOT**  
不得把时序过程中“未赋值即保持”描述成“防锁存”；锁存推断是组合覆盖不完整的问题。

### 7.2 Verilog-2001 兼容过程

**VSCS-PROC-005 — MUST**  
Verilog-2001 组合过程必须使用完整敏感列表，优先采用 `always @*`；时序与组合赋值规则必须与 VSCS-PROC-002 一致。

### 7.3 过程注释

**VSCS-PROC-006 — SHOULD**  
非平凡过程应按需说明：

- `Intent`：过程为何存在；
- `Assumption`：外部必须保证什么；
- `Invariant`：过程维持什么性质；
- `Latency`：可观察延迟；
- `Hazard`：最重要的非显然风险。

**VSCS-PROC-007 — SHOULD NOT**  
简单状态寄存器、直通组合逻辑等自解释过程不应强制套用长模板。

**VSCS-PROC-008 — MUST NOT**  
`@reads`、`@drives` 不得作为每个过程块的强制手工清单。所有权关系不显然时，可以用一句注释说明，并以 lint/elaboration 作为驱动关系的事实源。

---

## 8. FSM 专项要求

**VSCS-FSM-001 — MUST**  
FSM 文档必须说明：

- Moore、Mealy 或混合类型；
- 输出是组合还是寄存，以及接口可见延迟；
- 编码策略是 `auto`、`one_hot`、`binary/sequential`、`gray` 或用户编码；
- 非法状态处理策略；
- 依赖的厂商属性、约束或安全 FSM 功能。

**VSCS-FSM-002 — MUST NOT**  
本规范不得被解释为强制一段式、两段式或三段式 FSM，也不得统一强制 ONE-HOT。

**VSCS-FSM-003 — SHOULD**  
默认应允许工具自动选择编码；只有时序、面积、功耗、CDC、故障容错或安全分析提供依据时，才应固定编码。

**VSCS-FSM-004 — MUST**  
设计依赖特定编码时，必须施加对应工具约束，并在综合后报告中核验实际编码。

**VSCS-FSM-005 — MUST NOT**  
不得声称 ONE-HOT 本身保证无毛刺。无毛刺要求必须由寄存输出、经过验证的组合路径或接口协议保证。

**VSCS-FSM-006 — MUST NOT**  
不得仅凭 `case default` 宣称硬件能够从非法状态安全恢复。安全关键 FSM 必须核验综合后的非法状态检测/恢复逻辑，并通过仿真、形式验证或故障注入验证。

**VSCS-FSM-007 — MUST**  
FSM 的脉冲、握手或状态输出必须明确其相对状态转换的周期关系，避免把寄存输出的一周期延迟误写成同周期行为。

---

## 9. 复位与 RDC

**VSCS-RST-001 — MUST**  
每个时钟域必须独立定义复位策略，包括极性、断言方式、释放方式和目标时钟域。

**VSCS-RST-002 — MUST**  
异步复位若直接驱动目标域寄存器，必须异步断言并相对该目标时钟同步释放。

**VSCS-RST-003 — SHOULD**  
同一复位在同一目标时钟域应只同步一次，并使用统一的域内复位，避免逻辑在不同周期退出复位。

**VSCS-RST-004 — MUST**  
复位文档必须按适用情况说明：

- 极性；
- 同步或异步断言/释放；
- 目标时钟域；
- 同步级数及其选择依据；
- 最小有效脉宽；
- 释放时目标时钟必须运行的假设；
- 多复位之间的顺序和依赖；
- 所属 reset domain。

**VSCS-RST-005 — MUST NOT**  
复位同步级数不得在规范中机械固定为两级。项目必须根据器件、频率、可靠性目标和工具建议确定。

**VSCS-RST-006 — MUST**  
存在多个独立复位域时，项目必须执行 RDC 分析；同一时钟下的不同异步复位也必须纳入分析。

**VSCS-RST-007 — MUST**  
STA 必须覆盖适用的 recovery、removal 和 pulse-width 检查；注释不得替代复位时序约束。

**VSCS-RST-008 — SHOULD**  
设计应避免无必要地复位数据通路寄存器，特别是可能影响 RAM、SRL、DSP 或其他专用资源推断的场景。

---

## 10. CDC 专项要求

### 10.1 分类

**VSCS-CDC-001 — MUST**  
每条 CDC 在选择结构前必须分类为以下一种：

- 单比特稳定电平；
- 单比特脉冲或事件；
- 相互独立的多位标志；
- 需要原子一致性的多位数据；
- 单步递增/递减的计数器或指针；
- 连续数据流。

### 10.2 结构选择

**VSCS-CDC-002 — MUST**  
普通多级同步器只能用于单比特稳定电平，或彼此完全独立且不要求位间一致性的信号。

**VSCS-CDC-003 — MUST**  
脉冲或事件必须使用脉冲同步、toggle、握手或等效协议，并明确最小事件间隔、吞吐率和复位期间行为。

**VSCS-CDC-004 — MUST**  
需要位间原子一致性的多位数据必须使用握手、稳定数据加同步控制或异步 FIFO。

**VSCS-CDC-005 — MUST**  
Gray 同步只允许用于相邻值单步变化的计数器或指针，并必须配套位间 skew/最大路径延时约束及目标域采样条件验证。

### 10.3 文档字段

**VSCS-CDC-006 — MUST**  
CDC 文档必须按适用情况说明：

- 源时钟域和目标时钟域；
- 数据类别；
- 同步协议或结构；
- 同步级数；
- 延迟范围；
- 最小稳定时间、脉宽或事件间隔；
- 吞吐率；
- 复位行为和复位顺序；
- 丢失、重复、乱序及一致性假设；
- 厂商属性；
- 约束和验证报告的位置。

**VSCS-CDC-007 — MUST NOT**  
不得写“同步器消除亚稳态”。正确表述是：同步级增加亚稳态解析时间，使亚稳态传播概率满足项目可靠性目标。

**VSCS-CDC-008 — MUST**  
`ASYNC_REG` 等属性必须标明适用厂商和工具；属性不得被视为 CDC 协议正确性的证明。

**VSCS-CDC-009 — MUST**  
CDC 结构必须经过专用 CDC 工具或厂商 CDC 报告检查；所有 waiver 必须有可追溯编号和技术理由。

**VSCS-CDC-010 — SHOULD**  
项目应优先使用经过验证的厂商 CDC 宏/IP，以便工具识别结构、放置属性并执行误用检查。

**VSCS-CDC-011 — MUST**  
异步 FIFO 文档必须说明写侧和读侧复位顺序、ready/busy 约束、满空标志延迟及复位期间数据处理策略。

---

## 11. Doxygen 与文档工具

### 11.1 注释形式

**VSCS-DOC-001 — MUST**  
需要进入 Doxygen 文档的内容必须使用 Doxygen 特殊注释形式：

```systemverilog
/**
 * @brief 简短说明。
 */
```

或：

```systemverilog
/// @brief 简短说明。
```

**VSCS-DOC-002 — MUST NOT**  
普通 `// @brief` 不得被宣称为 Doxygen 文档块。

**VSCS-DOC-003 — MAY**  
`///<` 可以用于声明后的简短补充说明，但不应承载复杂接口契约或关键安全约束。

### 11.2 命令和解析边界

**VSCS-DOC-004 — MUST NOT**  
不得用 Doxygen 的 `@module` 表示 HDL module；该命令具有其他既定语义。

**VSCS-DOC-005 — MUST**  
`@clock`、`@reset`、`@domain`、`@latency`、`@hazard` 等自定义命令必须通过版本化的 `ALIASES` 配置定义；否则必须改用标准 `@par`、`@note` 或 `@warning`。

**VSCS-DOC-006 — MUST**  
项目若使用 Doxygen 处理 `.v`、`.sv` 或 `.svh`，必须版本化文件模式、扩展映射和必要的输入过滤器；不得假定 Doxygen 原生理解 SystemVerilog 结构语义。

**VSCS-DOC-007 — SHOULD**  
内嵌代码应使用 `@code ... @endcode`；`@example` 应只引用 `EXAMPLE_PATH` 中真实存在且最好经过编译检查的示例文件。

**VSCS-DOC-008 — MUST**  
Doxygen 生成成功只能证明文档语法和引用满足配置，不能证明 RTL 功能、CDC 或时序正确。

**VSCS-DOC-009 — SHOULD**  
文档配置应纳入版本控制，并在 CI 中将新增的未知命令、无效引用和解析警告作为失败处理。

**VSCS-DOC-010 — MUST NOT**  
不得把面向函数参数的 `@param` 直接当作 HDL parameter 的通用语义，也不得把 `@ports`、`@input` 或 `@output` 描述为 Doxygen 内建的 HDL 端口命令。项目过滤器或 `ALIASES` 明确定义时除外。

**VSCS-DOC-011 — SHOULD**  
Doxygen 配置应显式设置 `INPUT_ENCODING = UTF-8`，并与 VSCS-GEN-005 保持一致。

---

## 12. 工具职责与验证

**VSCS-VER-001 — MUST**  
项目必须为下列事实指定自动化验证手段：

| 工具阶段 | 最低职责 |
|---|---|
| 编译/elaboration | 语法、参数展开、端口连接、基本合法性 |
| lint | 位宽、符号、截断、组合覆盖、锁存、多驱动、编码规则 |
| 仿真/assertion/formal | 协议、状态转移、边界输入、复位行为和事件完整性 |
| CDC/RDC | 跨域结构、重汇聚、数据一致性和复位域关系 |
| 综合 | FSM 实际编码、同步寄存器识别、资源推断和属性生效 |
| STA | setup、hold、recovery、removal、pulse width 和约束完整性 |
| 文档生成 | 文档语法、引用和自定义命令 |

**VSCS-VER-002 — MUST NOT**  
`@reads`、`@drives`、`@hazard` 或其他注释字段不得替代上述工具检查。

**VSCS-VER-003 — MUST**  
每项影响签核的假设必须至少具有 assertion、约束、测试、工具报告或已批准人工分析中的一种验证证据。

**VSCS-VER-004 — MUST**  
未经批准的 unconstrained endpoint、CDC/RDC waiver、时序例外或文档警告不得被注释掩盖。

---

## 13. Code Review

Reviewer 必须区分人工检查和自动检查。

### 13.1 人工检查

**VSCS-REV-001 — MUST**  
Reviewer 必须确认注释说明了“为什么、依赖什么、接口如何观察、风险是什么”，而不是简单翻译代码。

**VSCS-REV-002 — MUST**  
Reviewer 必须检查接口契约与 RTL、约束、测试和报告是否一致。

**VSCS-REV-003 — MUST**  
涉及 FSM、复位、CDC 或 RDC 的修改，Reviewer 必须检查对应策略、延迟、属性和验证证据是否同步更新。

**VSCS-REV-004 — MUST**  
Reviewer 必须拒绝：

- 与代码矛盾或已经失效的注释；
- 无证据的绝对安全保证；
- 明显不完整的手工 `reads/drives` 清单；
- 未关联任务编号且无退出条件的长期 TODO；
- 将厂商属性描述为跨工具通用保证；
- 只存在于注释、没有执行机制的关键参数或协议约束。

### 13.2 自动检查

**VSCS-REV-005 — MUST**  
语法、位宽、latch、多驱动、CDC/RDC 结构、FSM 实际编码和时序结果必须以相应工具结果为合入依据。

---

## 14. 偏离与例外

**VSCS-EXC-001 — MUST**  
每项 `MUST` 或 `MUST NOT` 偏离必须记录：

- 唯一偏离编号；
- 被偏离的要求编号；
- 适用文件、模块、IP 或版本；
- 技术理由；
- 已知风险；
- 补偿措施及验证证据；
- 责任人和批准人；
- 到期日期或重新评审触发条件。

**VSCS-EXC-002 — MUST NOT**  
不得批准范围不明、永久有效且无重新评审条件的例外。

**VSCS-EXC-003 — MUST**  
涉及 CDC、RDC、复位释放、安全机制或外部接口契约的偏离必须由对应技术责任人批准。

**VSCS-EXC-004 — MUST**  
偏离到期或触发重新评审条件后必须重新批准或关闭；在此之前，相关对象为 `Non-compliant`。

偏离记录模板：

```markdown
## DEV-<编号>

- Requirement: VSCS-<AREA>-<NNN>
- Scope: <文件、模块、IP 或版本>
- Reason: <无法遵守的技术原因>
- Risk: <可能后果>
- Mitigation: <补偿措施及验证证据>
- Owner: <责任人>
- Approver: <批准人>
- Expires/Review trigger: <日期或触发条件>
- Status: Proposed | Approved | Closed
```

---

## 15. 版本与治理

**VSCS-GOV-001 — MUST**  
本规范使用 `MAJOR.MINOR.PATCH` 版本号：

- `MAJOR`：可能改变既有设计合规结论的规范性变更；
- `MINOR`：不使既有合规对象失效的可选能力、配置或资料性扩展；
- `PATCH`：不改变规范义务的勘误、澄清和排版修复。

**VSCS-GOV-002 — MUST**  
已发布版本必须保持不可变；任何修改必须发布为新版本。

**VSCS-GOV-003 — MUST**  
规范状态必须使用 `Draft`、`Active`、`Superseded` 或 `Withdrawn`。

| 状态 | 含义 |
|---|---|
| `Draft` | 征求意见，不作为正式签核基线 |
| `Active` | 当前有效且可以用于合规签核 |
| `Superseded` | 已被更新版本替代 |
| `Withdrawn` | 已撤回且不再适用 |

**VSCS-GOV-004 — MUST**  
规范变更必须说明受影响的要求编号、合规结果、工具检查、迁移影响和对应验证项。

**VSCS-GOV-005 — MUST**  
规范自身的变更历史必须由 Git 和发布记录保存，不得把完整修订历史复制进每个 RTL 文件。

**VSCS-GOV-006 — SHOULD**  
同一治理范围内应只有一个当前 `Active` 主版本。

---

## 16. 规范性模板

模板中的不适用段落必须删除。

本节代码是展示注释结构的资料性片段，不声明为完整可综合设计。对外发布“可直接使用”的示例时，仍须满足 VSCS-MOD-006。

### 16.1 文件与模块

```systemverilog
/**
 * @file
 * @brief 生成预分频计数事件和单周期溢出脉冲。
 *
 * @details
 * 本模块只负责时基计数，不负责跨时钟域传输输出事件。
 *
 * @par Interface contract
 * - `overflow_pulse` 在终值事件被接受后拉高一个 `clk` 周期。
 * - `enable` 必须与 `clk` 同步。
 *
 * @par Parameters
 * - `COUNTER_WIDTH`：位数，合法范围 2..32。
 * - `TOP_VALUE`：终值，合法范围 1..2^COUNTER_WIDTH-1。
 *
 * @par Clock and reset
 * - Clock: `clk`，上升沿。
 * - Reset: `rst_n`，异步断言、相对 `clk` 同步释放。
 *
 * @par Assumptions
 * - 非法参数值由 elaboration check 拒绝。
 *
 * @warning
 * 修改终值比较语义会改变事件周期，必须同步更新 assertion 和测试。
 */
module timer_base #(
    parameter int unsigned COUNTER_WIDTH = 16,
    parameter int unsigned TOP_VALUE     = 1000
) (
    input  logic clk,
    input  logic rst_n,
    input  logic enable,
    output logic overflow_pulse
);
```

### 16.2 非平凡时序过程

```systemverilog
// Intent: 更新计数状态并生成单周期终值事件。
// Invariant: overflow_pulse 只持续一个 clk 周期。
// Assumption: enable 已同步到 clk 域。
// Hazard: 修改比较条件会改变计数周期的定义。
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        count          <= '0;
        overflow_pulse <= 1'b0;
    end else begin
        overflow_pulse <= 1'b0;

        if (enable) begin
            if (count == TOP_VALUE - 1) begin
                count          <= '0;
                overflow_pulse <= 1'b1;
            end else begin
                count <= count + 1'b1;
            end
        end
    end
end
```

### 16.3 组合过程

```systemverilog
// Intent: 根据当前状态和输入协议计算次态。
// Default policy: 保持当前状态，只有满足显式条件时跳转。
always_comb begin
    state_next = state_curr;

    unique case (state_curr)
        IDLE: if (start) state_next = RUN;
        RUN : if (done)  state_next = DONE;
        DONE:             state_next = IDLE;
        default:          state_next = IDLE;
    endcase
end
```

### 16.4 FSM

```systemverilog
// FSM: Main control
// Type: Moore
// Style: two-process
// Encoding: auto; fixed encoding is not required by the interface.
// Reset state: IDLE
// Illegal-state policy: RTL fallback to IDLE; safety recovery, when required,
//                       is enabled and verified in the target synthesis flow.
// Output timing: done_pulse is registered and asserted on the RUN-to-DONE event.

typedef enum logic [1:0] {
    IDLE,
    RUN,
    DONE
} state_t;

state_t state_curr;
state_t state_next;

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        state_curr <= IDLE;
        done_pulse <= 1'b0;
    end else begin
        state_curr <= state_next;
        done_pulse <= (state_curr == RUN) && done;
    end
end
```

### 16.5 单比特稳定电平 CDC

以下代码只适用于单比特稳定电平。`dst_rst_n` 必须是目标域“异步断言、同步释放”的本地复位。

```systemverilog
// CDC: async_level
// Source domain: asynchronous or src_clk
// Destination domain: dst_clk
// Event model: stable single-bit level
// Mechanism: two-stage destination-domain synchronizer
// Latency: approximately 1..2 dst_clk periods after the input becomes stable
// Assumptions: input remains stable long enough to be sampled
// Constraints/verification: vendor synchronizer attribute + CDC report

// Replace this example attribute with the target tool's verified equivalent.
(* ASYNC_REG = "TRUE" *) logic [1:0] sync_ff;

always_ff @(posedge dst_clk or negedge dst_rst_n) begin
    if (!dst_rst_n) begin
        sync_ff <= '0;
    end else begin
        sync_ff <= {sync_ff[0], async_level};
    end
end

assign synced_level = sync_ff[1];
```

该结构增加亚稳态解析时间，但不“消除亚稳态”。脉冲、多位原子数据和连续数据流不得直接套用该模板。

### 16.6 CDC 说明模板

```systemverilog
// CDC: <信号或事务名称>
// Source domain: <源时钟域>
// Destination domain: <目标时钟域>
// Event model: level | pulse | toggle | atomic data | gray pointer | stream
// Mechanism: synchronizer | pulse/toggle handshake | gray | async FIFO
// Latency: <目标域周期范围或协议相关说明>
// Throughput/event gap: <最小事件间隔或持续吞吐率>
// Reset behavior: <两侧复位顺序及复位期间数据策略>
// Assumptions: <稳定时间、一致性、丢失/重复/乱序条件>
// Constraints/verification: <属性、约束和报告位置>
```

---

## 17. Code Review 检查表

```markdown
- [ ] 注释说明了设计意图、接口契约、假设、不变量或风险
- [ ] 参数单位、范围、边界及非法值处理明确
- [ ] 端口极性、时序、延迟、吞吐率和背压与实现一致
- [ ] 时钟域和复位策略明确
- [ ] FSM 类型、编码依据、输出时序和非法状态策略明确
- [ ] CDC 已分类，结构与数据类型匹配
- [ ] RDC、复位释放和 recovery/removal 已纳入检查
- [ ] 没有手工复制易漂移的 reads/drives、作者或修订历史
- [ ] 厂商属性注明了适用工具
- [ ] 关键假设具有 assertion、约束、测试或报告证据
- [ ] 示例由 CI 编译，或明确标为资料性伪代码
- [ ] 所有偏离均有有效批准记录
- [ ] Doxygen 启用时无新增未知命令或引用警告
```

---

## 18. 参考资料

### 18.1 规范性引用

- [IEEE Std 1800-2023 — SystemVerilog](https://standards.ieee.org/ieee/1800/7743/)
- [RFC 2119 — Key words for use in RFCs](https://www.rfc-editor.org/rfc/rfc2119)
- [RFC 8174 — Ambiguity of Uppercase vs Lowercase](https://www.rfc-editor.org/rfc/rfc8174)

### 18.2 资料性引用

- [Doxygen — Documenting the code](https://www.doxygen.nl/manual/docblocks.html)
- [Doxygen — Special commands](https://www.doxygen.nl/manual/commands.html)
- [Doxygen — Configuration](https://www.doxygen.nl/manual/config.html)
- [AMD Vivado Design Suite User Guide: Synthesis](https://docs.amd.com/r/en-US/ug901-vivado-synthesis)
- [AMD Vivado Design Analysis and Closure Techniques](https://docs.amd.com/r/en-US/ug906-vivado-design-analysis)
- [AMD Vivado Design Methodology](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology)
- [Intel Quartus Prime Pro Edition User Guides](https://www.intel.com/content/www/us/en/docs/programmable/)
- [Semantic Versioning 2.0.0](https://semver.org/)

---

## 19. 发布说明

### 1.0.0 — Draft — 2026-08-29

- 首次规范化发布。
- 修正 Doxygen 注释块和命令语义。
- 删除强制手工 `reads/drives` 和文件内 Revision History。
- 取消 FSM 三段式及 ONE-HOT 的普遍强制。
- 修正异步复位、非法状态恢复和 CDC 亚稳态表述。
- 增加 RDC、工具职责、合规模型及偏离治理。
