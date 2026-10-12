# Current-run arithmetic review — 212303

Completed outcome: `pipeline_arithmetic_review.json` records 409 new current-dump literal primitive quotes, verified against mapped_dump.v SHA256 `eaf0974fc723227dfa0f71717f3f2fc1c26d50689193ee816f0aba351b07b7f0`. Existing 4,875 pipeline evidence checks were not repeated. Arithmetic functions remain unresolved because an authoritative gop MODE binding was not found; no arithmetic truth mismatch was observed or claimed.

Resolved additional functions:

- CAM1 core_start's packed LUT matches `!N77 && (start || excess)` over all eight combinations of those named leaves.
- CAM2 N77 matches `overflow || overflow_reset` over all four combinations using its actual dual-LUT L6 output.
- All four core_valid registers take the exact combinational fire function: fire is the same cell's L6 output, core_valid is L6Q, QMUX_SEL=YX and clock enable is disabled. This proves one-edge capture of the actual fire function; the complete fire predicate still crosses unsupported operators.

| Concrete unresolved target | Exact boundary |
|---|---|
| CAM1 bitmap_work[145] | u_detector/N9386_3/gateop:Y |
| CAM2 bitmap_work[74] | u_detector/N11978_3/gateop:Y |
| CAM3 bitmap_work[146] | u_detector/N9578_3/gateop:Y |
| CAM4 bitmap_work[68] | u_detector/N12122_3/gateop:Y |
| CAM1/3/4 flush | adapter N77/gateop:Y, MODE=XOR |
| RGB565 luma / current_q arithmetic capture | Per-camera gopA/gopAL6Q INIT, carry and register cones in JSON arithmetic_cones |
| Absolute difference | Per-camera compare/subtract/carry cones in JSON arithmetic_cones |
| Full core_start/core_valid predicates | Named arithmetic boundary or occupancy/register leaves in adapter_predicate_tests and arithmetic_cones |

Every boundary retains actual type, MODE, INIT, input/output connections and a literal quote. Arithmetic-cone traversal lists external/registered leaves; it is structural evidence, not a behavioral PASS. Some traversal includes unused arithmetic-cell pins, so operator counts are cone witness counts rather than minimal functional dependency counts.

No ModelSim test was run: the installed simulation source provides V_/GTP_ primitives, but no behavioral gopA/gopAL6Q module was found. Substitution requires the missing MODE-to-carry-mux parameter binding. A vendor physical-primitive export specifying those muxes, or the vendor's documented operator behavioral binding, would make the four bitmap tests, 65,536 RGB565 cases, 65,536 byte-pair absolute differences and adapter control truth tests executable without inventing semantics. Publication predicates are owned by the separate reviewer.

Vendor semantic discovery: installed `arch/vendor/pango/titan2/common/valence/operator/gate/CLM/gopA.eval` and `gopAL6Q.eval` are binary operator definitions. Searching installed `.v/.vp/.sv/.vhd` files found no behavioral `module gopA` or `module gopAL6Q`. The readable `verilog/bsim/V_LUT6CARRY.v` implements two LUT5 tables, a CIN/I5-selected output mux and carry mux; `V_LUT6CARRY_E1.v` exposes a different three-mux parameterization. Neither has gop MODE parameters. A documented mapping of MODE=ARITH/ARITH1/XOR and AQ packing to these verification models is needed before treating either as a simulation replacement.

The installed packing rule `rule gopAQ` does establish that gopAL6Q combines a gopQ whose D is connected to gopA Y, preserving INIT and register properties. It does not disclose the gopA Y/COUT function.

Arithmetic decode is therefore unresolved pending a readable vendor operator binding, supported operator simulator, or a physical-primitive export with explicit carry mux parameters. No guessed scalar-LUT interpretation of arithmetic INIT has been used. Prior completed pipeline proofs and their 4,875 evidence entries are unchanged.

The following read-only extraction uses the existing report parser without executing its prior counter/count/evidence checks. It tests adapter predicates at explicitly named combinational boundaries; unsupported operators and register leaves are preserved as concrete blockers.

```python
from pathlib import Path
import re, json, hashlib
p=Path('log/100h_motion/four_actual_mapped_review.md')
code=re.search(r'```python\n(.*?)\n```',p.read_text(),re.S)[1]
ns={}
exec(code.split('for D in DS:')[0],ns)
rows=[]
for D in ns['DS']:
    A=D.rsplit('/u_detector',1)[0]
    row={'detector':D,'tests':{},'boundaries':[]}
    # A start/excess are combinational leaves. This test verifies their
    # registered combination/flush, not FIFO occupancy or event generation.
    tests=[('core_start',['start','excess','overflow','overflow_reset'],lambda v:bool(v&3) and not bool(v&12)),
           ('core_valid',['fire','overflow','overflow_reset'],lambda v:bool(v&1) and not bool(v&6)),
           ('N77',['overflow','overflow_reset'],lambda v:bool(v&3))]
    for target,inputs,expected in tests:
        n=1<<len(inputs)
        leaves={A+'/'+key:ns['column'](range(n),i) for i,key in enumerate(inputs)}
        leaves['ddr_init_done']=(1<<n)-1
        ev,mask,used=ns['evaluator'](leaves,n)
        net=A+'/'+target
        try:
            actual=ev(net) if target=='N77' else ns['next_data'](net,ev,mask)
            row['tests'][target]={'resolved':True,'matches':actual==sum(bool(expected(v))<<v for v in range(n)),'domain':n,'leaves':inputs}
        except ValueError as err:
            row['tests'][target]={'resolved':False,'reason':str(err),'leaves':inputs}
        ns['retain'](used)
        if net in ns['drivers']:ns['retain']([ns['drivers'][net][0]['instance']])
    for key in ('core_start','core_valid','N77'):
        net=A+'/'+key
        if net in ns['drivers']:
            x,pin=ns['drivers'][net];row['boundaries'].append({'target':key,'instance':x['instance'],'output_pin':pin,'kind':x['kind'],'parameters':x['parameters'],'ports':x['ports']})
    rows.append(row)
print(json.dumps(rows,indent=2))
```
