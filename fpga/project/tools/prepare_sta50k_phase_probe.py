"""Prepare (never execute) isolated PDS/TA constraint-installation probes.

Run generated scripts only after the other physical experiment completes.
No production file is read/written, no vendor tool process is started here.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--isolated-root", required=True, type=Path)
    args = p.parse_args()
    root = args.isolated_root.resolve()
    if "sta50k" not in root.name.lower() or "desktop" in str(root).lower():
        raise SystemExit("Expected the disposable sta50k isolated root")
    db = root / "place_route/hdmi_ddr_ov5640_top_pnr.adf"
    if not db.is_file():
        raise SystemExit("Isolated routed ADF is missing")
    out = root / "phase_install_probe"
    out.mkdir(exist_ok=True)
    db_tcl = "{" + db.as_posix() + "}"
    # TA exposes a separate report implementation; inspect actual help first.
    (out / "ta_help.tcl").write_text(
        'puts "TA_PHASE_REPORT_HELP_BEGIN"\nreport_timing -help\n'
        'puts "TA_PHASE_REPORT_HELP_END"\n'
        'puts "TA_PHASE_PATH_HELP_BEGIN"\nget_path_delay -help\n'
        'puts "TA_PHASE_PATH_HELP_END"\n', encoding="ascii")
    # FAMILY is a probe, not a claimed accepted option. Prior bare TA report
    # never initialized physical libraries, unlike the backend child action.
    (out / "ta_baseline_family.tcl").write_text(
        'puts "TA_PHASE_BASELINE_FAMILY_BEGIN"\n'
        'report_timing -family Logos -delay_type min_max -nworst 1 '
        '-max_path 3 -input_pins TRUE -report_exception TRUE\n'
        'puts "TA_PHASE_BASELINE_FAMILY_END"\n', encoding="ascii")
    # Documented -input_db_file branch may initialize the native timing action.
    (out / "ta_baseline_inputdb.tcl").write_text(
        'puts "TA_PHASE_BASELINE_INPUTDB_BEGIN"\n'
        f'report_timing -input_db_file {db_tcl} -delay_type min_max '
        '-nworst 1 -max_path 3 -input_pins TRUE -report_exception TRUE\n'
        'puts "TA_PHASE_BASELINE_INPUTDB_END"\n', encoding="ascii")
    # Supported backend file-format conversion. Output is a disposable new
    # file, never a modified routed DB. Inspect it for a complete SDC section.
    (out / "backend_dump_db.tcl").write_text(
        'set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484\n'
        f'.switch_db -input {db_tcl} -output {{{(out / "routed_text.adf").as_posix()}}}\n', encoding="ascii")
    manifest = {
        "state": "PREPARED_NOT_EXECUTED",
        "db": str(db), "db_sha256": hashlib.sha256(db.read_bytes()).hexdigest(),
        "requirement": "Wait for physical-experiment completion notification; no overlapping vendor runtime",
        "steps": [
            "TA help only: establish options of its report_timing implementation.",
            "Run exactly one baseline variant matching that help; stop if E: or crash.",
            "Convert copied ADF to disposable text with backend_dump_db.tcl, inspect full constraints.",
            "Only if baseline reporting works: install FIFO path candidate in TA Tcl and rerun, prove report changes.",
            "If full SDC export exists: append audited candidate to full SDC, then test documented DB+SDC override.",
            "Do not run PNR or adopt a production phase flow until constraint enforcement is demonstrated.",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
    ta = "C:/pango/PDS_2022.2-SP6.4/bin/ta.exe"
    shell = "C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe"
    lines = [
        "# PREPARED ONLY. Run after completion notification, one stage at a time.",
        "# TA -tcl is synchronous when launched with Start-Process -Wait.",
    ]
    for name in ("ta_help", "ta_baseline_family", "ta_baseline_inputdb"):
        lines.append(
            f"# {name}: inspect preceding help before baseline selection.\n"
            f"Start-Process '{ta}' -ArgumentList '{db.as_posix()} "
            f"-rtr {out.as_posix()} -tcl {(out / (name + '.tcl')).as_posix()}' "
            f"-Wait -PassThru -RedirectStandardOutput '{(out / (name + '_stdout.txt')).as_posix()}' "
            f"-RedirectStandardError '{(out / (name + '_stderr.txt')).as_posix()}'")
    lines.append(
        f"& '{shell}' -file '{(out / 'backend_dump_db.tcl').as_posix()}' "
        f"-work_dir '{out.as_posix()}' -project_name backend_dump_db "
        f"*> '{(out / 'backend_dump_db_stdout.txt').as_posix()}'")
    (out / "commands_review_only.ps1").write_text("\n\n".join(lines) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
