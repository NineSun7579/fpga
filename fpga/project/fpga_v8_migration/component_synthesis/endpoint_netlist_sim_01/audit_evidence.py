"""Independently audit saved simulation evidence without rerunning any tool."""
import collections
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    results = json.loads((HERE / "results.json").read_text())
    commands = json.loads((HERE / "commands.json").read_text())
    before = json.loads((HERE / "protected_before.json").read_text())
    after = json.loads((HERE / "protected_after.json").read_text())
    models = json.loads((HERE / "official_models.json").read_text())
    assert results["status"] == "PASS"
    assert before == after
    assert all(sha(Path(p)) == digest for p, digest in before.items())
    assert all(sha(Path(p)) == digest for p, digest in results["inputs"].items())
    assert all(sha(Path(item["path"])) == item["sha256"] for item in models["files"])
    assert len(commands) == 8 and all(c["returncode"] == 0 for c in commands)
    assert all(Path(c["cwd"]).is_relative_to(HERE) for c in commands)
    assert {Path(c["argv"][0]).name for c in commands} == {"vlib.exe", "vlog.exe", "vsim.exe"}
    # The mapped compile contains only official cells and the original .vm.
    mapped_compile = commands[5]["argv"]
    assert mapped_compile[-1].endswith("fpga_v8_endpoint_ctrl_synth_syn.vm")
    assert mapped_compile[3:-1] == [item["path"] for item in models["files"]]
    assert all(Path(p).parent == Path(models["installation"]) for p in mapped_compile[3:-1])
    assert not any("fpga_v8_coop_control_axil.v" in p for p in mapped_compile)
    assert not any("fpga_v8_coop_axi128_endpoint.v" in p for p in mapped_compile)
    traces = [(HERE / variant / "actual.trace").read_bytes() for variant in ("rtl", "mapped")]
    assert traces[0] == traces[1]
    counts = collections.Counter()
    bresp = collections.Counter()
    rresp = collections.Counter()
    bids, rids = set(), set()
    complete_reads = 0
    for line in traces[1].decode("ascii").splitlines():
        f = line.split()
        counts[f[1]] += 1
        assert not any("x" in v.lower() or "z" in v.lower() for v in f[2:])
        if f[1] == "B":
            bids.add(int(f[2], 16))
            bresp[int(f[3], 16)] += 1
        if f[1] == "R":
            rids.add(int(f[2], 16))
            rresp[int(f[4], 16)] += 1
            complete_reads += int(f[5], 16)
    assert bids == rids == set(range(128))
    assert dict(counts) == results["mapped"]["channel_counts"]
    for variant in ("rtl", "mapped"):
        assert results[variant]["operations"] == results["operations"] == 654
        assert results[variant]["protocol_errors"] == 0
        assert all(results[variant][key] > 0 for key in
                   ("b_stall_cycles", "r_stall_cycles", "cmd_stall_cycles", "release_stall_cycles"))
        assert "Errors: 0" in (HERE / variant / "tool_3.log").read_text()
    report = {"status": "PASS", "protected_existing_files_rechecked": len(before),
              "official_model_files_rechecked": len(models["files"]),
              "netlist_cell_instances": sum(models["netlist_cell_instances"].values()),
              "rtl_mapped_public_traces_byte_identical": True,
              "public_events_per_variant": sum(counts.values()), "channel_counts": dict(counts),
              "complete_writes_per_variant": counts["B"], "complete_reads_per_variant": complete_reads,
              "reset_abandoned_aw_per_variant": counts["AW"] - counts["B"],
              "reset_abandoned_ar_per_variant": counts["AR"] - complete_reads,
              "b_responses": {"OKAY": bresp[0], "SLVERR": bresp[2]},
              "r_response_beats": {"OKAY": rresp[0], "SLVERR": rresp[2]},
              "unique_b_ids": len(bids), "unique_r_ids": len(rids)}
    (HERE / "evidence_audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
