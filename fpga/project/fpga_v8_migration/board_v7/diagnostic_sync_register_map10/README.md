# Site-only PAP_LOC 实际映射探针

map09实际基线映射已完成，位置臂报ConstraintEditor-0048：impl_devCQ0是无效器件symbol。此前把routed PLACE的实现名字当作PAP_LOC symbol并无官方依据。该失败保留，本次去掉symbol，只给两个不同CLMA site。

依据：官方UCE §2.3.4.6描述PAP_LOC可取device instance名字；PCE §4.13.1示例有不带primitive symbol的site约束；实际def_inst_site -help明确sym_name可选。未预称能够防打包。

为了避免重复编译，本次复用map09两个实验臂实际compile/synthesis图、ADF与native DB。逐项核验原artifact/hash文件并重新审计D/Q/CLK/C/INIT/GRS/CE及串联连接；准备工程、RTL和clock逐字节与旧执行输入对应，仅site.lcf改变。reuse_provenance.json记录所有原阶段身份，不伪造本次compile/synthesis回执。site.lcf在actual_map.tcl中由add_constraint交给dev_map。

两臂各自复制真实synthesize目录到隔离执行目录，再实际dev_map与switch_db导出图；位置臂必须同时取得独立单元、完整寄存器语义、原生PCF实际单元site绑定及同单元映射PAP_LOC/CDB条目。所有输入/失败保留，生产60门禁仍BLOCKED。成功最多为PASS_METHOD_ONLY，不是新bit交付。
