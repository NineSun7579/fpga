from pathlib import Path
import hashlib, json, shutil, difflib

root = Path(__file__).resolve().parents[3]
base = root / 'project/sim/sfp_tx_recovery'
out = root / 'project/sim/sfp_tx_head_pipeline'
prod = root / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
out.mkdir(exist_ok=True)
assert not (out / 'archived_original/sfp_video_tx.v').exists(), 'Already prepared: preserve the baseline archive; do not regenerate after production changes'
for folder in ['candidate', 'archived_original']:
    (out / folder).mkdir(exist_ok=True)
original = (prod / 'sfp_video_tx.v').read_bytes()
(out / 'archived_original/sfp_video_tx.v').write_bytes(original)
for folder in ['candidate', 'archived_original']:
    shutil.copy2(prod / 'video_async_fifo.v', out / folder / 'video_async_fifo.v')
newline = b'\r\r\n' if b'\r\r\n' in original else b'\r\n' if b'\r\n' in original else b'\n'
stage = '''    // Capture the pre-pop FIFO head; consume it once on the next fabric edge.
    reg [18:0] head_q;
    reg head_valid_q;
    reg head_go_q;
    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n) begin
            head_q       <= 19'b0;
            head_valid_q <= 1'b0;
            head_go_q    <= 1'b0;
        end else begin
            head_valid_q <= `UD fifo_pop;
            head_go_q    <= `UD tx_go;
            if (fifo_pop)
                head_q <= `UD fifo_rdata;
        end
    end
    wire consume_head = head_valid_q;
    wire payload_go = tx_go && head_go_q;

'''.encode().replace(b'\n', newline)
marker = b'    wire head_vs = fifo_rdata[18];'
assert original.count(marker) == 1
prefix, suffix = original.split(marker)
suffix = marker + suffix
suffix = suffix.replace(b'fifo_rdata', b'head_q').replace(b'fifo_pop', b'consume_head')
assert suffix.count(b'if (!tx_go)') == 1
suffix = suffix.replace(b'if (!tx_go)', b'if (!payload_go)')
assert suffix.count(b'txd        <= `UD idle_word;') == 1
suffix = suffix.replace(b'txd        <= `UD idle_word;', b"txd        <= `UD 32'hBC0028BC;")
candidate = prefix + stage + suffix
(out / 'candidate/sfp_video_tx.v').write_bytes(candidate)
for name in ['run.ps1', 'run_full.ps1', 'recovery_config.sv']:
    shutil.copy2(base / name, out / name)
tb = (base / 'tb_tx_recovery.sv').read_text()
start = tb.index('    bit must_block, have_pop;')
end = tb.index('    integer used_tx;', start)
tb = tb[:start] + '''    // Independent one-cycle model of the raw FIFO pop/head/readiness.
    // Never use the DUT's head stage or recovery authorization state.
    bit must_block, have_pop;
    bit model_valid=0, model_go=0;
    reg [18:0] model_head=0;
    reg [1:0] consumed_ctrl;
    integer fid;
    always @(posedge fab_clk) begin
        if(!rst_n) begin
            blocked=1; previous_go=0;
            model_valid=0; model_go=0; model_head=0;
        end else begin
            if(!tx.tx_go || !model_go) begin
                blocked=1;
                if(previous_go) ever_down=1;
                if(model_valid) down_pops++;
            end
            must_block=blocked;
            have_pop=model_valid;
            consumed_ctrl={model_head[17],model_head[18]};
            if(tx.tx_go && model_go && model_valid && !model_head[16] && model_head[18]) begin
                if(blocked && ever_down) begin
                    recovered=model_head[15:12]; recover_count++;
                end
                blocked=0;
            end
            previous_go=tx.tx_go && model_go;
            model_valid=tx.fifo_pop;
            model_go=tx.tx_go;
            if(tx.fifo_pop) model_head=tx.fifo_rdata;
            #2;
            if(must_block && txk==0) begin
                forbidden_words++;
                if(ever_down) postfault_words++;
                fail("payload before ready-high consumed VS boundary");
            end
            if(must_block && have_pop && (txk!==9 || txd[22:21]!==consumed_ctrl))
                fail("discarded input controls not propagated");
        end
    end
''' + tb[end:]
(out / 'tb_tx_recovery.sv').write_text(tb)
diff = ''.join(difflib.unified_diff(original.decode('latin1').splitlines(True), candidate.decode('latin1').splitlines(True), fromfile='production/sfp_video_tx.v', tofile='candidate/sfp_video_tx.v'))
(out / 'candidate.diff').write_text(diff, encoding='utf8')
hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [prod/'sfp_video_tx.v', prod/'video_async_fifo.v', out/'candidate/sfp_video_tx.v']}
(out / 'initial_hashes.json').write_text(json.dumps(hashes, indent=2))
print(out)
