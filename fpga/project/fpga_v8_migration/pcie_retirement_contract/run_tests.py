"""Isolated frozen PCIe FIFO + real controller + official Pango FIFO regression.

Generated RTL is an artifact derived from frozen input, never a production edit.
Only the external PCIe shell and the AXI route/memory responder are modeled.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / "whole_candidate" / "inputs"
MOTION = HERE.parent.parent / "motion_100h"
FIFO_REL = Path("source/pcie_dma/pcie_fifo.v")
CTRL_REL = Path("source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_controller.v")
FIFO_SHA = "c6bcf1f48328ff250e097ad1bbe0e49e8e52001138fe15f9db697da1ddf62027"
CTRL_SHA = "0ff0f5c28650e8eb91da5bc39a26c6498874cafe0b51ccfa1847872c3cbacc53"
PANGO = Path(os.environ.get("PANGO_SIM", r"C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation"))
SIM = Path(os.environ.get("MODELSIM_BIN", r"C:\modeltech64_10.6e\win64"))
ART = HERE / "artifacts"

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def identities():
    out = {}
    for root in (INPUTS, MOTION):
        for rel, expected in ((FIFO_REL, FIFO_SHA), (CTRL_REL, CTRL_SHA)):
            p = root / rel
            out[str(p)] = sha(p)
            assert out[str(p)] == expected, (p, out[str(p)])
    for p in sorted((INPUTS / "ipcore" / "pcie_rx_fifo").rglob("*.v")):
        out[str(p)] = sha(p)
    for p in sorted((INPUTS / "ipcore" / "pcie_tx_fifo").rglob("*.v")):
        out[str(p)] = sha(p)
    for p in (PANGO / "GTP_DRM36K_E1.v", PANGO / "GTP_GRS.v",
              HERE.parent / "cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v",
              HERE.parent / "cooperative_control/fpga_v8_coop_control_axil.v"):
        out[str(p)] = sha(p)
    return out

def tool(cmd, cwd, label):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    text = result.stdout + result.stderr
    (cwd / (label + ".log")).write_text(text, encoding="utf-8")
    if result.returncode or "** Error" in text or "** Fatal" in text:
        raise RuntimeError(f"{label}: {text[-10000:]}")
    return text

def declaration_compatibility(source, extra):
    """ModelSim rejects frozen forward references; hoist declarations only.

    wire declaration assignments remain continuous assignments at the same
    location. All procedural bodies and RHS expressions are byte-identical.
    """
    declarations = []
    def move(match):
        decl = match[0]
        clean = re.sub(rb'/\*.*?\*/', b'', decl, flags=re.S)
        if b'=' in clean and not clean.lstrip().startswith(b'localparam'):
            assert clean.lstrip().startswith(b'wire'), decl
            left, rhs = clean[:-1].split(b'=', 1)
            name = re.search(rb'(\w+)\s*$', left)[1]
            declarations.append(left.rstrip()+b';')
            return b'assign '+name+b' ='+rhs+b';'
        declarations.append(decl)
        return b''
    body = re.sub(rb'(?m)^(?:wire|reg|localparam)\s+[^;]*;', move, source)
    # First semicolon terminates the parameter/port declaration header.
    at = body.index(b');')+2
    block = b'\n// Simulation compatibility: declarations hoisted only.\n'
    block += b'\n'.join(declarations + extra)+b'\n'
    return body[:at]+block+body[at:], declarations

def prepare_baseline():
    pairs = [(FIFO_REL, [b'wire fifo_rx_almost_full;']),
             (CTRL_REL, [b'wire total_length_cfg_done;'])]
    manifest = {}
    for rel, extra in pairs:
        source = (INPUTS / rel).read_bytes()
        prepared, moved = declaration_compatibility(source, extra)
        target = ART / ("compat_"+rel.name)
        target.write_bytes(prepared)
        manifest[str(rel)] = dict(original_sha256=hashlib.sha256(source).hexdigest(),
                                  compat_sha256=sha(target),
                                  declarations_hoisted=len(moved),
                                  explicit_existing_implicit_nets=[x.decode() for x in extra])
    (ART / "compatibility.json").write_text(json.dumps(manifest, indent=2)+"\n")

def prepare_candidate():
    source = (INPUTS / FIFO_REL).read_bytes()
    candidate = source.replace(b'module pcie_fifo #(', b'module fpga_v8_pcie_fifo_retired #(', 1)
    line_end = b'\r\n' if b'\r\n' in source else b'\n'
    insertion = (HERE / "retirement_insert.vh").read_bytes().replace(b'\r\n', b'\n')
    insertion = insertion.replace(b'\n', line_end)
    at = candidate.index(b');')+2
    candidate = candidate[:at]+line_end+insertion+candidate[at:]
    old = b'fpga_rx_done <= fifo_rx_empty;'
    new = (b'// Final completion needs the new transaction\'s last accepted B.'+line_end+
           b'            if (fifo_rx_empty && (rx_retired_sync2 != rx_retired_seen))'+line_end+
           b'                fpga_rx_done <= 1\'b1;')
    assert candidate.count(old) == 1
    candidate = candidate.replace(old, new, 1)
    # No other behavior changes, including all TX/F2H and intermediate chunks.
    assert candidate[candidate.index(b'//////////////tx/////////////////'):] == source[source.index(b'//////////////tx/////////////////'):]
    header = lambda b: b[:b.index(b');')+2].split(b'#(',1)[1]
    assert header(candidate) == header(source), "parameter/port API changed"
    target = ART / "fpga_v8_pcie_fifo_retired.v"
    target.write_bytes(candidate)
    compat, moved = declaration_compatibility(candidate, [b'wire fifo_rx_almost_full;'])
    (ART / "compat_fpga_v8_pcie_fifo_retired.v").write_bytes(compat)
    import difflib
    diff = ''.join(difflib.unified_diff(source.decode('gbk',errors='replace').splitlines(True),
                                      candidate.decode('gbk',errors='replace').splitlines(True),
                                      fromfile='frozen/pcie_fifo.v',
                                      tofile='candidate/fpga_v8_pcie_fifo_retired.v'))
    (ART / "candidate.diff").write_text(diff, encoding="utf-8")
    return dict(candidate_sha256=sha(target),port_parameter_api_identical=True,
                entire_tx_axi_write_read_suffix_identical=True,
                compat_declarations_hoisted=len(moved))

def compile_dut(kind):
    cwd = ART / kind
    cwd.mkdir(parents=True, exist_ok=True)
    tool([str(SIM / "vlib.exe"), "work"], cwd, "vlib")
    if kind == 'baseline':
        # Preserve the exact-byte compilation failure as part of the evidence.
        attempt=subprocess.run([str(SIM/'vlog.exe'),'-permissive','-work','work',
                                str(INPUTS/FIFO_REL),str(INPUTS/CTRL_REL)],
                               cwd=cwd,capture_output=True,text=True,
                               encoding='utf-8',errors='replace',timeout=120)
        (cwd/'direct_frozen_compile.log').write_text(attempt.stdout+attempt.stderr,encoding='utf-8')
        assert attempt.returncode and 'Undefined variable' in attempt.stdout
    sources = [PANGO / "GTP_DRM36K_E1.v", PANGO / "GTP_GRS.v"]
    for name in ("pcie_rx_fifo", "pcie_tx_fifo"):
        folder = INPUTS / "ipcore" / name
        sources += sorted((folder / "rtl").glob("ipm*.v"))
        sources += [folder / (name + ".v")]
    sources += [ART / "compat_ips2l_pcie_dma_controller.v",
                HERE.parent / "cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v",
                HERE.parent / "cooperative_control/fpga_v8_coop_control_axil.v"]
    fifo = ART / "compat_pcie_fifo.v" if kind == "baseline" else ART / "compat_fpga_v8_pcie_fifo_retired.v"
    sources += [fifo]
    # Frozen legacy Verilog uses implicit nets/forward declarations; compile
    # in its original language mode, then compile only the TB as SystemVerilog.
    tool([str(SIM / "vlog.exe"), "-work", "work"] + [str(p) for p in sources], cwd, "vlog_rtl")
    cmd = [str(SIM / "vlog.exe"), "-sv", "-work", "work"]
    if kind == "candidate": cmd += ["+define+FIFO_MODULE=fpga_v8_pcie_fifo_retired"]
    tool(cmd + [str(HERE / "tests/pango_pcie_top_stub.sv"),
                str(HERE / "tests/tb_pcie_retirement.sv")], cwd, "vlog_tb")
    return cwd

def run_case(cwd, mode):
    text = tool([str(SIM / "vsim.exe"), "-c", "-voptargs=+acc", "-onfinish", "stop",
                 "work.tb_fpga_v8_pcie_retirement", f"+MODE={mode}",
                 "-do", "run -all; quit -f"], cwd, f"mode_{mode}")
    assert "RETIREMENT_TB_DONE" in text, text
    events = (cwd / "events.trace").read_text().splitlines()
    (cwd / f"mode_{mode}.trace").write_text("\n".join(events)+"\n")
    return events

def read_events(path):
    ops = defaultdict(lambda: defaultdict(list))
    for line in path.read_text().splitlines():
        fields = line.split()
        op, time, channel = int(fields[0]), int(fields[1]), fields[2]
        ops[op][channel].append((time, fields[3:]))
    return ops

def check_control(kind, ops):
    report = []
    expected = {1:(0x30,0,0),2:(0x40,0,0),3:(0x44,0x10203040,0),
                4:(0x48,0x11223344,0),5:(0x4c,1,0),6:(0x30,0,2),
                7:(0x4c,1,2),8:(0x40,0x12345678,0),10:(0x40,0xcafebabe,0)}
    for op, (offset, word, resp) in expected.items():
        events = ops[op]
        for channel in ('AW','W','CAW','CW','E_BVALID','B','MSI'):
            assert len(events[channel]) == 1, (kind,op,channel,events[channel])
        assert int(events['AW'][0][1][0],16) == 0x40010000+offset*4
        assert int(events['AW'][0][1][1],16) == 0
        assert int(events['W'][0][1][0],16)&0xffffffff == word
        assert events['W'][0][1][1:] == ['ffff','1']
        assert int(events['CAW'][0][1][0],16) == offset
        assert int(events['CW'][0][1][0],16) == word
        assert [int(x,16) for x in events['B'][0][1]] == [0,resp]
        msi, b, eb = events['MSI'][0][0], events['B'][0][0], events['E_BVALID'][0][0]
        assert b-eb >= 230000, (kind,op,'B hold too short')
        if kind == 'candidate':
            assert msi > b, (kind,op,'MSI before B',msi,b)
        else:
            assert msi < b, (kind,op,'negative fixture missing',msi,b)
        report.append(dict(operation=op,local_offset=hex(offset),full_bresp=resp,
                           msi_time_ps=msi,full_b_time_ps=b,
                           msi_minus_b_ps=msi-b))
    claim = next(time for time,words in ops[1]['BANK'] if words==['3'])
    ack = next(time for time,words in ops[5]['BANK'] if words==['0'])
    assert (ops[1]['MSI'][0][0] > claim) == (kind=='candidate')
    assert (ops[5]['MSI'][0][0] > ack) == (kind=='candidate')
    assert ops[9]['PENDING_RESET'] and not ops[9]['B']
    assert len(ops[9]['MSI']) == (0 if kind=='candidate' else 1)
    return report

def check_memory(kind, op, events, total, host=0x01000000):
    assert len(events['W']) == (total+15)//16, (kind,op,'W count',len(events['W']))
    assert len(events['AW']) == (total+255)//256
    assert len(events['B']) == len(events['AW'])
    assert len(events['MSI']) == 1 and not events['TIMEOUT']
    for index, (time, words) in enumerate(events['W']):
        available = min(16,total-index*16)
        expected = bytes((((index*16+j)*37+11)&255) if j<available else 0 for j in range(16))
        assert int(words[0],16) == int.from_bytes(expected,'little'), (kind,op,index,words[0],expected.hex())
        expected_strb=(1<<available)-1
        assert int(words[1],16) == expected_strb, (kind,op,index,'STRB')
        assert int(words[2]) == int(index%16==15 or index==(total+15)//16-1)
    crossing=[]
    for index, (time, words) in enumerate(events['AW']):
        addr,length = int(words[0],16),int(words[1],16)
        assert addr == 0x08000000+index*256, (kind,op,index,'AW address',hex(addr))
        assert length == min(16,(total+15)//16-index*16)-1
        if addr%4096+(length+1)*16>4096: crossing.append(hex(addr))
    assert not crossing
    fetch_crossing=[]
    assert len(events['FETCH']) == (total+4095)//4096
    for index, (time, words) in enumerate(events['FETCH']):
        addr,length,chunk = int(words[0],16),int(words[1],16),int(words[2])
        assert addr == host+index*4096
        assert chunk == min(4096,total-index*4096)
        wire_bytes = length*4 if length else 4096
        if addr%4096+wire_bytes>4096: fetch_crossing.append(hex(addr))
    msi=events['MSI'][0][0];final_b=events['B'][-1][0]
    assert (msi>final_b) == (kind=='candidate')
    return dict(operation=op,payload_bytes=total,w_beats=len(events['W']),
                full_b_responses=len(events['B']),pcie_fetch_chunks=len(events['FETCH']),
                all_data_and_strobes_match=True,final_b_time_ps=final_b,
                msi_time_ps=msi,msi_minus_final_b_ps=msi-final_b,
                pcie_4kb_violations=fetch_crossing)

def audit_results(kinds):
    result = dict(scope='official Pango FIFO/DRM + frozen control logic, simulation external PCIe shell',
                  verdict='FROZEN_EARLY_COMPLETION_REPRODUCED',implementations={})
    for kind in kinds:
        folder=ART/kind
        control=read_events(folder/'mode_0.trace')
        memory=read_events(folder/'mode_1.trace')
        offset=read_events(folder/'mode_2.trace')
        stalled=read_events(folder/'mode_3.trace')[40]
        wrong=read_events(folder/'mode_4.trace')[50]
        control_report=check_control(kind,control)
        memory_report=[check_memory(kind,op,memory[op],total)
                       for op,total in ((20,4092),(21,4100),(22,1228800))]
        offset_report=check_memory(kind,30,offset[30],8192,0x01000004)
        assert len(offset_report['pcie_4kb_violations']) == 2
        assert stalled['TIMEOUT'] and not stalled['W'] and not stalled['B']
        assert len(stalled['MSI']) == (0 if kind=='candidate' else 1)
        assert len(wrong['B']) == 1 and wrong['B'][0][1]==['1','0']
        if kind=='candidate': assert wrong['TIMEOUT'] and not wrong['MSI']
        else: assert len(wrong['MSI'])==1
        for mode,op in ((3,41),(4,51)):
            recovered=read_events(folder/f'mode_{mode}.trace')[op]
            assert len(recovered['W'])==len(recovered['B'])==len(recovered['MSI'])==1
            assert int(recovered['W'][0][1][0],16)&0xffffffff == 0xabcdef01
            assert recovered['B'][0][1]==['0','0']
            assert (recovered['MSI'][0][0]>recovered['B'][0][0]) == (kind=='candidate')
        result['implementations'][kind]=dict(control=control_report,memory=memory_report,
            offset4_negative=offset_report,
            legacy_post_aw_w_stall='TIMEOUT_NO_MSI' if kind=='candidate' else 'TIMEOUT_EARLY_MSI',
            wrong_bid='TIMEOUT_NO_MSI' if kind=='candidate' else 'EARLY_MSI',
            stalled_w_and_wrong_bid_common_reset_recovery=True,
            pending_b_common_reset='NO_COMPLETION_LEAK' if kind=='candidate' else 'EARLY_MSI_BEFORE_RESET')
    if 'candidate' in kinds:
        result['verdict']='FINAL_B_RETIREMENT_GATE_PASS_WITH_LEGACY_LIMITATIONS'
    (ART/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()
    before = identities()
    ART.mkdir(exist_ok=True)
    (ART / "hashes_before.json").write_text(json.dumps(before, indent=2)+"\n")
    prepare_baseline()
    baseline = compile_dut("baseline")
    for mode in range(5):
        run_case(baseline, mode)
        print(f"baseline mode {mode} completed", flush=True)
    if not args.baseline_only:
        candidate_manifest = prepare_candidate()
        candidate = compile_dut("candidate")
        for mode in range(5):
            run_case(candidate, mode)
            print(f"candidate mode {mode} completed", flush=True)
        (ART / "candidate_manifest.json").write_text(json.dumps(candidate_manifest, indent=2)+"\n")
    results=audit_results(['baseline'] if args.baseline_only else ['baseline','candidate'])
    after = identities()
    assert before == after
    (ART / "hashes_after.json").write_text(json.dumps(after, indent=2)+"\n")
    print("Frozen input hashes unchanged. "+results['verdict'])

if __name__ == "__main__":
    main()
