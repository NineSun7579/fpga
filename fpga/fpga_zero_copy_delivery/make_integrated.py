"""Generate only the isolated FPGA source/project; never run PDS or access a board."""
from pathlib import Path
import difflib
import hashlib
import json
import os
import re
import shutil
import integrate_display

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'fpga_acceleration_delivery/ddr_rgb_letterbox/integrated'
OUT = ROOT / 'integrated'
EXCLUDED = ('npu', 'pcie2npu')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def retired_tieoffs():
    # These are request-side outputs of removed masters, never AXI slave ready
    # or command-completion inputs. Reused S05/S06/M02 must remain untouched.
    fields = {'awid': 4, 'awaddr': 32, 'awlen': 4, 'awsize': 3,
              'awburst': 2, 'awlock': 1, 'awcache': 4, 'awprot': 3,
              'awvalid': 1, 'wdata': 128, 'wstrb': 16, 'wlast': 1,
              'wvalid': 1, 'bready': 1}
    values = {f'npu_out_axi_{name}': f"{width}'d{int(name == 'bready')}"
              for name, width in fields.items()}
    fields = {'arid': 4, 'araddr': 32, 'arlen': 4, 'arsize': 3,
              'arburst': 2, 'arlock': 1, 'arcache': 4, 'arprot': 3,
              'arvalid': 1, 'rready': 1}
    for port in range(3):
        values.update({f'npu_s{port}_axi_{name}': f"{width}'d{int(name == 'rready')}"
                       for name, width in fields.items()})
    return values


def patch_top(raw):
    start = raw.index(b'// ===== NPU removed: tie off crossbar-facing NPU ports =====')
    end = raw.index(b'// M02 (NPU register window) response inputs', start)
    old = raw[start:end]
    # Fail if this baseline grows an active owner in the retired block.
    assigned = re.findall(rb'assign\s+(\w+)\s*=', old)
    assert set(assigned) == {n.encode() for n in (
        'npu_out_axi_awvalid', 'npu_out_axi_wvalid', 'npu_out_axi_bready',
        'npu_s0_axi_arvalid', 'npu_s0_axi_rready', 'npu_s1_axi_arvalid',
        'npu_s1_axi_rready', 'npu_s2_axi_arvalid', 'npu_s2_axi_rready')}
    text = '// Legacy FPGA NPU absent: deterministic inactive master requests.\n'
    text += '// Response READY only drains stale responses; no command success is generated.\n'
    text += '// S05 = cam1 KF history, S06 = delivery reads, M02 = delivery MMIO.\n'
    text += ''.join(f'assign {name} = {value};\n' for name, value in retired_tieoffs().items())
    return raw[:start] + text.encode('ascii') + b'\n' + raw[end:]


def main():
    # Refuse before touching candidate files if the other agent's real endpoint
    # is unavailable. No empty module/blackbox is substituted.
    display_dir = ROOT / 'display_scaler'
    integrate_display.validate_endpoint(display_dir)
    original_project = (BASE / 'project/project.pds').read_bytes()
    # Input project already excludes NPU; fail rather than silently remove a
    # newly active dependency or pretend a missing accelerator accepted work.
    refs = re.findall(rb'\((?:_file|_ip|_ip_source_item) "([^"]+)"', original_project)
    assert not any(b'/npu/' in p or b'/pcie2npu/' in p for p in refs)
    snapshots = {p: digest(p.read_bytes()) for p in (BASE / 'source').rglob('*') if p.is_file()}
    snapshots[BASE / 'project/project.pds'] = digest(original_project)
    excluded = []
    copied = {}
    for path, before in snapshots.items():
        if path == BASE / 'project/project.pds':
            continue
        relative = path.relative_to(BASE)
        if relative.parts[1] in EXCLUDED:
            excluded.append(str(relative).replace('\\', '/'))
            continue
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied[str(relative).replace('\\', '/')] = before
    top_path = BASE / 'source/top.v'
    original = top_path.read_bytes()
    candidate = patch_top(original)
    (OUT / 'source/top.v').write_bytes(candidate)
    changes = {'source/top.v': (original, candidate)}
    for relative, transform in (
        ('source/delivery/delivery_regs.v', integrate_display.regs),
        ('source/delivery/delivery_top_adapter.v', integrate_display.adapter)):
        old = (BASE / relative).read_bytes()
        new = transform(old)
        (OUT / relative).write_bytes(new)
        changes[relative] = (old, new)
    for name in integrate_display.DISPLAY_FILES:
        target = OUT / 'source/display' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(display_dir / name, target)
    (ROOT / 'display_integration.diff').write_text(''.join(
        ''.join(difflib.unified_diff(old.decode('gbk', 'replace').splitlines(True),
                                   new.decode('gbk', 'replace').splitlines(True),
                                   fromfile='letterbox/integrated/' + name,
                                   tofile='integrated/' + name))
        for name, (old, new) in changes.items()), encoding='utf-8')
    (ROOT / 'legacy_npu_top.v.diff').write_text(''.join(difflib.unified_diff(
        original.decode('gbk', 'replace').splitlines(True),
        candidate.decode('gbk', 'replace').splitlines(True),
        fromfile='letterbox/integrated/source/top.v', tofile='integrated/source/top.v')), encoding='utf-8')
    project_dir = OUT / 'project'
    project_dir.mkdir(parents=True, exist_ok=True)
    # Reference existing IP inputs. Do not copy compile/synthesis/P&R artifacts.
    def rebase(match):
        value = match[1]
        if value.startswith((b'../ipcore/', b'ipcore/')):
            target = BASE / 'project' / value.decode('ascii')
            assert target.exists(), target
            return b'"' + os.path.relpath(target, project_dir).replace('\\', '/').encode('ascii') + b'"'
        return match[0]
    project = integrate_display.project_entries(re.sub(rb'"([^"]+)"', rebase, original_project))
    (project_dir / 'project.pds').write_bytes(project)
    pcf = BASE / 'device_map/top.pcf'
    if pcf.exists():
        (OUT / 'device_map').mkdir(exist_ok=True)
        shutil.copy2(pcf, OUT / 'device_map/top.pcf')
    source_refs = re.findall(rb'\((?:_file|_ip|_ip_source_item) "([^"]+)"', project)
    inputs = [p for p in source_refs if b'/source/' in p or b'/ipcore/' in p or p.startswith(b'ipcore/')]
    assert all((project_dir / p.decode('ascii')).exists() for p in inputs)
    for name, value in retired_tieoffs().items():
        assignments = re.findall(rb'assign\s+' + name.encode() + rb'\s*=\s*([^;]+);', candidate)
        assert assignments == [value.encode()], (name, assignments)
    # Project-selected ordinary RTL cannot reference any excluded module type.
    legacy_modules = set()
    for relative in excluded:
        legacy_modules.update(re.findall(rb'\bmodule\s+(\w+)', (BASE / relative).read_bytes()))
    for relative in inputs:
        if not relative.endswith(b'.v'):
            continue
        raw = (project_dir / relative.decode()).read_bytes()
        raw = re.sub(rb'/\*.*?\*/|//[^\r\n]*', b'', raw, flags=re.S)
        for module in legacy_modules:
            assert not re.search(rb'\b' + module + rb'\b\s+(?:#\s*\([^;]*?\)\s*)?\w+\s*\(', raw), (relative, module)
    assert all(digest(p.read_bytes()) == before for p, before in snapshots.items())
    unchanged = [name for name, before in copied.items() if digest((OUT / name).read_bytes()) == before]
    assert len(unchanged) == len(copied) - len(changes)
    report = {'baseline': str(BASE), 'project': str(project_dir / 'project.pds'),
              'baseline_already_has_no_legacy_NPU_instance_or_project_entries': True,
              'modified_RTL': sorted(changes), 'byte_identical_other_source_files': len(unchanged),
              'modified_RTL_sha256': {name: {'before': digest(old), 'after': digest(new)}
                                      for name, (old, new) in changes.items()},
              'added_display_RTL': ['source/display/' + name for name in integrate_display.DISPLAY_FILES],
              'display_endpoint_sha256': {name: digest((display_dir / name).read_bytes()) for name in integrate_display.DISPLAY_FILES},
              'display_scope': 'cam5 lease only; six camera capture and RAW RK3568 inference retained',
              'mode_controls': {'capabilities_offset': '0xa0, value 3', 'mode_offset': '0xb0, RGB=0 thumbnail=1',
                                'RGB_destination': '0x0a000000', 'thumbnail_destination': '0x0a200000',
                                'mode_write': 'full strobe, idle, capture_hold=0, not quarantined'},
              'top_before_sha256': digest(original), 'top_after_sha256': digest(candidate),
              'excluded_source_files': sorted(excluded),
              'excluded_module_types': sorted(m.decode() for m in legacy_modules),
              'retired_tieoffs': retired_tieoffs(), 'resolved_project_input_references': len(inputs),
              'IP_policy': 'relative references to baseline IP; no IP edits or build artifacts copied',
              'NPU_resource_saving_vs_baseline': 'none established; already excluded',
              'RK3568_inference': 'unchanged; viewer not modified', 'pds_run': False, 'board_access': False}
    (ROOT / 'legacy_npu_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('retired_tieoffs', 'excluded_source_files', 'excluded_module_types')}, indent=2))


if __name__ == '__main__':
    main()
