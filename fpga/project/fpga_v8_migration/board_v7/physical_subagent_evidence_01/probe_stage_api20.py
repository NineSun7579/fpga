"""Top-level runtime help, avoiding unsupported editor and Tcl-loop preparse."""
from native_query08 import run

if __name__ == '__main__':
    run('stage_api20', '''set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
open_project -help
save_project -help
generate_constraint -help
.switch_db -help
dev_map -help
''')
