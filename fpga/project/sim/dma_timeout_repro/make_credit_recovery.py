from pathlib import Path
p=Path(__file__).parent
b=(p/'tb_frame_recovery.sv').read_bytes()
b=b.replace(b'module tb_frame_recovery;',b'module tb_credit_recovery;\n wire [15:0] available;')
b=b.replace(b'.dma_abort_req(abort_req),',b'.dma_abort_req(abort_req),.axi_data_available(available),')
b=b.replace(b'.BURST_LEN(16),.WD_LIMIT(64)',b'.BURST_LEN(16),.WAIT_FOR_DATA(1),.WD_LIMIT(64)')
b=b.replace(b'.data_in(data),',b'.data_in_available(available),.data_in(data),')
b=b.replace(b"send_frame('h6000,13);sof();",b"send_frame('h6000,129);repeat(10)@(negedge clk);sof();")
# Explicitly check that insufficient stored data never reserves shared DDR.
b=b.replace(b"send_frame('h4000,11);failed_frame(a,t,s);",b"send_frame('h4000,11);repeat(20)@(negedge clk);if(av||bus_active)$fatal(1,\"partial pre-AW source reserved DDR\");failed_frame(a,t,s);")
(p/'tb_credit_recovery.sv').write_bytes(b)
for mode in ['frame_recovery','frame_recovery_vendor']:
 b=(p/(mode+'.do')).read_bytes().replace(b'tb_frame_recovery',b'tb_credit_recovery')
 b=b.replace(b'work_recovery',b'work_credit_recovery').replace(b'work_vendor',b'work_credit_vendor')
 (p/(mode.replace('frame_','credit_')+'.do')).write_bytes(b)
