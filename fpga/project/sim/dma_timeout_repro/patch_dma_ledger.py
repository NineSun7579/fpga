from pathlib import Path
import hashlib

root = Path(__file__).resolve().parents[2]
p = root / 'source/axi_dma/axi_dma_write.v'
original = p.read_bytes()
backup = p.with_name(p.name + '.ledger.bak')
if backup.exists():
    raise SystemExit('Backup already exists; refusing to overwrite or reapply')
nl = b'\r\n' if b'\r\n' in original else b'\n'
s = original.replace(b'\r\n', b'\n')

def replace(old, new):
    global s
    old, new = old.encode('ascii'), new.encode('ascii')
    if s.count(old) != 1:
        raise SystemExit('Expected unique patch anchor: ' + repr(old))
    s = s.replace(old, new)

replace("\tif((cmd_ready == 1'b1) && (cmd_valid == 1'b1))begin\n\t\tlen <=", "\tif(rst == 1'b1)begin\n\t\tlen <= 32'd0;\n\tend\n\telse if((cmd_ready == 1'b1) && (cmd_valid == 1'b1))begin\n\t\tlen <=")
replace("len <= 32'd0;       // [WD]", "len <= 32'd0;       // Discard only unissued remainder after real B.")
replace("trans <= 1'b0;      // [WD] release the stuck transaction", "trans <= 1'b0;      // Aborted burst has completed external W and B.")
replace("\t\t\telse if(abort_done == 1'b1)begin\n\t\t\t\tburst_trans <= 1'b0;   // [WD2] force-release; B may never arrive\n\t\t\tend\n", "")
replace("if((burst_trans == 1'b0) && (len != 32'd0) && (abort_r == 1'b0))begin", "if((trans == 1'b1) && (burst_trans == 1'b0) && (len != 32'd0) && (abort_r == 1'b0))begin")
replace("\tm_axi_awlen <= max_burst_len - 8'd1;", "\tif(!m_axi_awvalid) m_axi_awlen <= max_burst_len - 8'd1;")
replace("\tm_axi_awaddr <= addr;", "\tif(!m_axi_awvalid) m_axi_awaddr <= addr;")
replace("(trans == 1'b0) || (abort_r == 1'b1) || (w_progress == 1'b1)", "(burst_trans == 1'b0) || (abort_r == 1'b1) || (w_progress == 1'b1)")
start = s.index(b'// [BFAST 2026-09-19]')
end = s.index(b'// ---------------------------------------------------------------------------------', start)
s = s[:start] + b'''// Timeout may fill an accepted burst, but cannot cancel an advertised AW
// or fabricate completion. Waiting AW and waiting B retain their ledger.
always @(posedge clk) begin
    if(rst == 1'b1)
        abort_r <= 1'b0;
    else if(abort_done == 1'b1)
        abort_r <= 1'b0;
    else if(!abort_r && burst_trans && (act_burst_len != 0)
            && !w_progress && (wd_cnt == 24'hFFFFFF))
        abort_r <= 1'b1;
end

// BREADY is asserted only after the external final W handshake below.
assign abort_done = abort_r && m_axi_bvalid && m_axi_bready;
''' + s[end:]
replace("if((t_m_axi_wvalid == 1'b1) && (t_m_axi_wready == 1'b1) && (t_m_axi_wlast == 1'b1)) begin", "if((m_axi_wvalid == 1'b1) && (m_axi_wready == 1'b1) && (m_axi_wlast == 1'b1)) begin")
start = s.index(b'// [LEDGER 2026-09-19]')
end = s.index(b'reg trans_q;', start)
s = s[:start] + b'// One completion per command, only after its final real B handshake.\n' + s[end:]
patched = s.replace(b'\n', nl)
# All anchors checked before the first write. Preserve the original exact bytes.
backup.write_bytes(original)
assert backup.read_bytes() == original
p.write_bytes(patched)
print('backup:', backup)
print('before SHA256:', hashlib.sha256(original).hexdigest())
print('after  SHA256:', hashlib.sha256(patched).hexdigest())
