"""Run existing fabric simulations using this candidate and actual top tieoffs."""
from pathlib import Path
import importlib
import json
import re
import sys
import importlib.util

from make_integrated import BASE, OUT, ROOT, retired_tieoffs


def main():
    sys.path.insert(0, str(BASE.parent))
    tests = importlib.import_module('run_integration_tests')
    oracle = importlib.import_module('run_tests').oracle
    artifacts = ROOT / 'legacy_npu_verification'
    artifacts.mkdir(exist_ok=True)
    lib = artifacts / 'work'
    def run(args, name):
        return tests.run(args, artifacts / name, cwd=artifacts)
    if not lib.exists():
        run([tests.BIN / 'vlib.exe', lib], 'vlib.log')
    project = (OUT / 'project/project.pds').read_bytes()
    design = project[project.index(b'(_widget wgt_my_design_src'):project.index(b'(_widget wgt_my_ips_src')]
    sources = [(OUT / 'project' / p.decode()).resolve() for p in re.findall(rb'\(_file "([^"]+)"', design)]
    legacy = {'top.v', 'ips2l_pcie_dma.v', 'ips2l_pcie_dma_controller.v', 'pango_pcie_top.v', 'pcie_fifo.v'}
    checked = [p for p in sources if p.name not in legacy]
    run([tests.BIN / 'vlog.exe', '-work', lib, '-vlog01compat', *checked], 'fabric_compile.log')
    tb = tests.testbench()
    # Existing unknown-register check moves because +a0 now advertises modes.
    tb = tb.replace("mmio_read(32'ha0,value); // exact register decode",
                    "mmio_read(32'hc0,value); // exact register decode")
    tb = tb.replace('        mmio_read(0,value);', '''
        mmio_read(32'ha0,value); if(value!=3) $fatal(1,"FAIL capabilities");
        mmio_read(32'hb0,value); if(value!=0) $fatal(1,"FAIL default RGB mode");
        mmio_read(32'h40,value); if(value!=32'h0a000000) $fatal(1,"FAIL RGB destination");
        mmio_read(32'h60,value); if(value!=W*OH*3) $fatal(1,"FAIL RGB byte count");
        expected_bresp=2; mmio_write(32'hb0,2); // invalid mode
        expected_bresp=0; mmio_write(32'hb0,1);
        mmio_read(32'hb0,value); if(value!=1) $fatal(1,"FAIL thumbnail mode");
        mmio_read(32'h40,value); if(value!=32'h0a200000) $fatal(1,"FAIL thumbnail destination");
        mmio_read(32'h60,value); if(value!=(W/2)*(H/2)*2) $fatal(1,"FAIL thumbnail byte count");
        expected_bresp=2; mmio_write(32'h40,32'h0a000000); // wrong mode destination
        host_wstrb=1; mmio_write(32'hb0,0); host_wstrb=65535; // partial mode write
        expected_bresp=0; mmio_write(32'hb0,0);
        mmio_read(0,value);''', 1)
    tb = tb.replace("        mmio_write(32'h20,1);", """        mmio_write(32'h20,1);
        expected_bresp=2; mmio_write(32'hb0,1); // mode locked by capture lease
        expected_bresp=0;
        mmio_read(32'hb0,value); if(value!=0) $fatal(1,"FAIL held mode changed");""", 1)
    top = (OUT / 'source/top.v').read_bytes()
    declarations = []
    for name, value in retired_tieoffs().items():
        width = int(value.split("'")[0])
        declarations.append(f"wire {f'[{width-1}:0] ' if width > 1 else ''}{name};")
        assignment = re.search(rb'assign\s+' + name.encode() + rb'\s*=[^;]+;', top)[0].decode()
        declarations.append(assignment)
        if name.startswith('npu_out_axi_'):
            port = 's02_axi_' + name[len('npu_out_axi_'):]
        else:
            port = f's0{int(name[5])+2}_axi_' + name.split('_axi_')[1]
        tb, count = re.subn(r'\.' + port + r'\([^)]*\)', f'.{port}({name})', tb)
        assert count == 1, (port, count)
    tb = tb.replace('module tb_delivery_integration;',
                    'module tb_delivery_integration;\n' + '\n'.join(declarations))
    tb_path = artifacts / 'tb_delivery_integration.sv'
    tb_path.write_text(tb, encoding='ascii')
    run([tests.BIN / 'vlog.exe', '-work', lib, '-sv', tb_path,
         BASE.parent / 'sim/tb_delivery_camera_hold.sv'], 'tb_compile.log')
    for width in (4, 64):
        (artifacts / 'expected.hex').write_text(''.join(f'{b:02x}\n' for frame in range(2)
                                                       for b in oracle(width, 3, 5, 1, frame)))
        log = run([tests.BIN / 'vsim.exe', '-c', '-quiet', '-onfinish', 'exit', '-lib', lib,
                   'tb_delivery_integration', f'-gW={width}', '-do',
                   'onerror {quit -code 2}; run -all; quit -code 0'], f'integration_w{width}.log')
        assert 'PASS tb_delivery_integration' in log
    log = run([tests.BIN / 'vsim.exe', '-c', '-quiet', '-onfinish', 'exit', '-lib', lib,
               'tb_delivery_camera_hold', '-do', 'onerror {quit -code 2}; run -all; quit -code 0'],
              'camera_hold.log')
    assert 'PASS production camera admission' in log
    from display_integration_testbench import testbench as thumbnail_testbench
    thumb_tb = artifacts / 'tb_thumbnail_integrated.sv'
    thumb_tb.write_text(thumbnail_testbench(tests.build.MMIO), encoding='ascii')
    run([tests.BIN / 'vlog.exe', '-work', lib, '-sv', thumb_tb], 'thumbnail_tb_compile.log')
    spec = importlib.util.spec_from_file_location('display_endpoint_fixture', ROOT / 'display_scaler/run_ddr_test.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    thumbnail_results = []
    for name, width, height, stall, hold, fault in (
        ('full_tail_drain', 640, 480, 0, 0, 0),
        ('full_final_b_hold', 640, 480, 1, 1, 0),
        ('read_fault_owner_retained', 64, 16, 1, 0, 1),
        ('write_fault_owner_retained', 64, 16, 1, 0, 2)):
        folder = artifacts / name
        folder.mkdir(exist_ok=True)
        source = b''.join(fixture.pixel(x, y).to_bytes(2, 'little')
                          for y in range(height) for x in range(width))
        golden = b''.join(source[2*(y*width+x):2*(y*width+x)+2]
                          for y in range(0, height, 2) for x in range(0, width, 2))
        (folder / 'source_physical.hex').write_text(''.join(f'{b:02x}\n' for b in fixture.native_memory(source, 0xd3)), encoding='ascii')
        log = tests.run([tests.BIN / 'vsim.exe', '-c', '-quiet', '-onfinish', 'exit', '-lib', lib,
                         'tb_thumbnail_integrated', f'-gW={width}', f'-gH={height}',
                         f'-gSTALL={stall}', f'-gHOLD_B={hold}', f'-gFAULT={fault}',
                         '-do', 'onerror {quit -code 2}; run -all; quit -code 0'], folder / 'simulation.log', cwd=folder)
        assert 'PASS DDR:' in log
        actual = bytes(int(line, 16) for line in (folder / 'dest_physical.hex').read_text().splitlines())
        assert actual == fixture.native_memory(golden, 0xa5, guard=64), name
        thumbnail_results.append({'case': name, 'payload_bytes_compared': len(golden),
                                  'physical_bytes_including_guards': len(actual)})
        print('PASS integrated thumbnail:', name, flush=True)
    report = {'ordinary_project_RTL_compiled': len(checked),
              'not_ModelSim_compiled_PDS_legacy_files': sorted(legacy),
              'simulation': 'existing MMIO/crossbar/7-master DDR integration with actual 44 retired top tieoffs',
              'checks': ['six competing camera writers', 'byte exact RGB letterbox, W=4 and W=64',
                         'MMIO backpressure/error response', 'busy/queued/unpublished freeze rejection',
                         'camera admission hold and resume', 'default RGB and capabilities/mode/size controls',
                         'per-mode immutable destination, partial/invalid/held/busy mode write rejection',
                         'real thumbnail core MMIO launch, AXI mux, quarantine and return to RGB'],
              'thumbnail_native_memory_results': thumbnail_results,
              'full_top_vendor_IP_elaboration': 'not run; PDS parent task',
              'pds_run': False, 'board_access': False}
    (artifacts / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
