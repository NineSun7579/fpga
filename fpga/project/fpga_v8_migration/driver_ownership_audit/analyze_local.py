"""Hash retained inputs and inspect existing ELF only; never build code."""
import hashlib
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]

def main():
    paths=set((PROJECT/'hardware_acceleration/dma_export/retained').rglob('*'))
    for directory in ['migration/RK3568_PG100H-release/RK3568/master/AI_NPU/driver','migration/RK3568_PG100H-release/RK3568/master/AI_car_pro_npu/driver','deploy']:
        paths.update((PROJECT/directory).glob('*'))
    paths.update([PROJECT/'fpga_v8_migration/board/live_dma_layout_20261005.json',PROJECT/'DOC/cam3_dma_board_20260926.md',PROJECT/'DOC/cam3_diag_20260926_round3_reboot.md'])
    manifest=[]
    for path in sorted(paths):
        if not path.is_file(): continue
        data=path.read_bytes()
        manifest.append({'path':str(path.relative_to(PROJECT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        if path.suffix in ['.c','.h'] and 'pango_pci_driver' in path.name:
            dest=ROOT/'local_sources'/str(path.relative_to(PROJECT)).replace('\\','__').replace('/','__')
            dest.parent.mkdir(exist_ok=True); dest.write_bytes(data)
    (ROOT/'local_input_hashes.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    selected={'pango_cdev_open','pango_cdev_release','pango_cdev_ioctl','pango_cdev_mmap','read_img','read_npu','pango_irq_handler0','pango_irq_handler1','pango_irq_handler2'}
    for module in [ROOT/'board_files/003_pango_pci_driver_fixed_20260926.ko',ROOT/'board_files/002_pango_pci_driver_baseline.ko']:
        with module.open('rb') as f:
            elf=ELFFile(f); symtab=elf.get_section_by_name('.symtab'); lines=[]
            symbols=list(symtab.iter_symbols()); relocations={}
            for section in elf.iter_sections():
                if section['sh_type'] not in ['SHT_RELA','SHT_REL']: continue
                for rel in section.iter_relocations():
                    symbol=symbols[rel['r_info_sym']]
                    relocations[(section['sh_info'],rel['r_offset'])]=symbol.name+' '+str(rel.entry.get('r_addend',0))
            engine=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
            for symbol in symbols:
                if symbol.name not in selected or not isinstance(symbol['st_shndx'],int): continue
                section=elf.get_section(symbol['st_shndx']); start=symbol['st_value']; size=symbol['st_size']
                lines.append('\nFUNCTION '+symbol.name+' section='+section.name+' offset='+hex(start)+' bytes='+str(size))
                for ins in engine.disasm(section.data()[start:start+size],start):
                    annotation=relocations.get((symbol['st_shndx'],ins.address),'')
                    lines.append(f'{ins.address:08x}: {ins.mnemonic:8} {ins.op_str:36} {annotation}')
            (ROOT/(module.stem+'_disassembly.txt')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
            dwarf=elf.get_dwarf_info(); sources=[]
            for cu in dwarf.iter_CUs():
                top=cu.get_top_DIE(); attrs=top.attributes
                sources.append({k:attrs[k].value.decode(errors='replace') for k in ['DW_AT_name','DW_AT_comp_dir','DW_AT_producer'] if k in attrs})
            (ROOT/(module.stem+'_dwarf.json')).write_text(json.dumps(sources,indent=2)+'\n',encoding='utf-8')
    print('Local source manifests and existing ELF disassembly saved.')
if __name__=='__main__': main()
