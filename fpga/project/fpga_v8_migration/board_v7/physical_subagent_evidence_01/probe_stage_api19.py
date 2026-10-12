"""Discover documented editor/stage interfaces without modifying an input DB."""
from native_query08 import run

if __name__ == '__main__':
    run('stage_api19', '''set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
foreach cmd {editor save_adif add_constraint export_fdc} {
    puts "STAGE_API19_BEGIN $cmd"
    set code [catch {$cmd -help} value]
    puts "STAGE_API19_RESULT $cmd $code $value"
}
puts "STAGE_API19_COMMANDS [lsort [info commands]]"
''')
