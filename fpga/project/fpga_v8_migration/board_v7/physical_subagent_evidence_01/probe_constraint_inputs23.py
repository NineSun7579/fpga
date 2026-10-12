"""Query actual supported netlist/constraint input interfaces."""
from native_query08 import run

if __name__ == '__main__':
    run('constraint_inputs23', '''set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
gen_netlist -help
add_sources -help
add_design -help
prj2tcl -help
''')
