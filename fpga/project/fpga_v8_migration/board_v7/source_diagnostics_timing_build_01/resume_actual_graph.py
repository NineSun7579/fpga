"""Post-PNR rederive from the actual final synthesis DB; never mutate running project."""
import traceback
from pathlib import Path
from physical_flow import HERE, EVIDENCE, wait_idle, protected, export_graph, derive, runtime_constraints, record, status
from preflight import load, require, sha

def main():
    wait_idle(); protected()
    route = HERE / 'place_route/v7_sdt_top_pnr.adf'
    require(sha(route) == load(EVIDENCE / 'pnr_artifact.json')['sha256'], 'Routed DB drift')
    cg, ca = export_graph('compile_final_pnr', HERE / 'compile/v7_sdt_top_comp.adf', False)
    sg, sa = export_graph('actual_final_pnr', HERE / 'synthesize/v7_sdt_top_syn.adf', True)
    # Derive into a scratch constraint destination, preserve the exact routed inputs.
    original = (HERE / 'constraints_candidate/clock.fdc').read_bytes()
    # Read-only graph derivation uses the same algorithm with output redirected.
    import physical_flow
    source = Path(physical_flow.__file__).read_text(encoding='utf8')
    section = source[source.index('def derive('):source.index('def runtime_constraints(')]
    section = section.replace("dest = HERE / 'constraints_candidate/clock.fdc'", "dest = EVIDENCE / 'clock_final_graph_candidate.fdc'")
    section = section.replace("(EVIDENCE / 'clock_imported_candidate.fdc').write_bytes(dest.read_bytes())", "(EVIDENCE / 'clock_final_graph_candidate.fdc').write_bytes(original_clock)")
    section = section.replace("record('input_hashes.json', snapshot())", "record('final_pnr_graph_derivation.json', {'read_only': True})")
    scope = dict(vars(physical_flow));scope['original_clock'] = original
    exec(compile(section, str(physical_flow.__file__), 'exec'), scope)
    proof = scope['derive'](cg, sg, sa)
    require((HERE / 'constraints_candidate/clock.fdc').read_bytes() == original, 'Read-only graph audit changed constraints')
    record('coverageproof_final_pnr_synthesis.json', proof)
    record('final_graph_constraint_comparison.json', {
        'same_generated_bytes': (EVIDENCE / 'clock_final_graph_candidate.fdc').read_bytes() == original,
        'final_syn_sha256': sha(HERE / 'synthesize/v7_sdt_top_syn.adf'),
        'physical_pairs': proof['physical_pairs'], 'route_sha256': sha(route)})
    runtime_constraints(proof, sg)
    status('FINAL_PNR_GRAPH_DERIVED_PHYSICAL_BINDING_REVIEW_REQUIRED')

if __name__ == '__main__':
    try:
        main()
    except BaseException:
        (EVIDENCE / 'final_graph_failure.txt').write_text(traceback.format_exc(), encoding='utf8')
        status('FINAL_GRAPH_REVIEW_FAILED')
        raise
