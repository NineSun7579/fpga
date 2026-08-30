# Compile Pango USIM/VSIM libraries for the selected simulator and family.
# All machine-specific values are supplied by compile_simlib.ps1 as env vars.

proc env_or_default {name default_value} {
    if {[info exists ::env($name)] && $::env($name) ne ""} {
        return $::env($name)
    }
    return $default_value
}

set project_root [file normalize "[file dirname [info script]]/.."]
set simlib_dir [file normalize [env_or_default PDS_SIMLIB_DIR "$project_root/build/simlib"]]
set simulator [env_or_default PDS_SIMULATOR "QuestaSim Simulator"]
set family [env_or_default PDS_FAMILY "Logos2"]
set language [env_or_default PDS_LANGUAGE "Verilog"]
set library [env_or_default PDS_LIBRARY "BOTH"]
set simulator_exec_path [file normalize [env_or_default PDS_SIMULATOR_EXEC_PATH "C:/questasim64/win64"]]

file mkdir $simlib_dir

puts "INFO: compiling Pango simulation libraries"
puts "INFO: simulator=$simulator family=$family language=$language library=$library"
puts "INFO: simulator executable path=$simulator_exec_path"
puts "INFO: output directory=$simlib_dir"

compile_simlib \
    -Simulator $simulator \
    -family $family \
    -language $language \
    -library $library \
    -simulator_exec_path $simulator_exec_path \
    -directory $simlib_dir

puts "INFO: simulation library compilation completed"
