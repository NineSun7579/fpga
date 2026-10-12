`timescale 1ns/1ps
module tb_fpga_v8_capture_endpoint;
    reg clk=0;always #5 clk=!clk;
    reg rst_n=0;
    integer cycle=0,op=0,trace,stim,rc,code;
    reg [31:0] a[0:11];
    reg [6:0] awid=0,arid=0;
    reg [31:0] awaddr=0,araddr=0;
    reg [7:0] awlen=0,arlen=0;
    reg [2:0] awsize=4,arsize=4,awprot=0,arprot=0;
    reg [1:0] awburst=1,arburst=1;
    reg awvalid=0,wvalid=0,arvalid=0,wlast=0,bready=0,rready=0;
    reg [127:0] wdata=0;
    reg [15:0] wstrb=0;
    wire awready,wready,bvalid,arready,rvalid,rlast;
    wire [6:0] bid,rid;
    wire [1:0] bresp,rresp;
    wire [127:0] rdata;
    wire [31:0] ea,ed,era;
    wire [2:0] ep,erp;
    wire [3:0] es;
    wire eav,ewv,ebr,erv,err,ear,ewr,ebv,erar,errv;
    wire [1:0] ebp,errp;
    wire [31:0] erd;
    wire [31:0] ca[0:1],cd[0:1],cra[0:1],crd[0:1];
    wire [2:0] cp[0:1],crp[0:1];
    wire [3:0] cs[0:1];
    wire [1:0] cbp[0:1],crresp[0:1];
    wire cav[0:1],cwv[0:1],cbr[0:1],crav[0:1],crr[0:1];
    wire car[0:1],cwr[0:1],cbv[0:1],crar[0:1],crv[0:1];
    wire cawr[0:1],cwwr[0:1],cbvalid[0:1],carready[0:1],crvalid[0:1];
    wire ea_gate=(cycle%7>=3),ew_gate=(cycle%11>=6);
    wire ga[0:1],gw[0:1],gb[0:1],gra[0:1],gr[0:1];
    reg hold_capture_b=0;
    genvar g;
    generate for(g=0;g<2;g=g+1) begin: stalls
        assign ga[g]=cycle%13>=6+g;
        assign gw[g]=cycle%17>=9-g;
        assign gb[g]=cycle%19>=12-g && !(g==1 && hold_capture_b);
        assign gra[g]=cycle%5==g;
        assign gr[g]=cycle%23>=17-g;
        assign car[g]=cawr[g] && ga[g];
        assign cwr[g]=cwwr[g] && gw[g];
        assign cbv[g]=cbvalid[g] && gb[g];
        assign crar[g]=carready[g] && gra[g];
        assign crv[g]=crvalid[g] && gr[g];
    end endgenerate
    wire router_awready,router_wready;
    assign ear=router_awready && ea_gate;
    assign ewr=router_wready && ew_gate;

    wire cfgv,cfgr,cfga,cfge,epoch,armed,cfgok,fault,lease_block;
    wire [31:0] cfggen,published,failed,mreject;
    wire [1:0] bank0,bank1;
    reg engine_idle=1,capture_bank=0,sof_attempt=0,publish=0,retired_error=0;
    wire admitted_sof=sof_attempt && !lease_block;
    reg [31:0] publish_seq=0;
    wire iv,ir,raw_valid,hv,hr;
    wire [31:0] src_addr,src_len,src_seq,src_gen,hs,hl,hseq,hgen;
    wire [2:0] src_cam,hcam;
    wire src_bank,hbank;
    wire [63:0] src_token,htoken;
    wire hrv,hrr,hra,hre;
    wire [2:0] hrcam;
    wire hrbank;
    wire [31:0] hrseq,hrgen;
    wire [63:0] hrtoken;
    reg corrupt_release=0;
    wire [63:0] manager_host_release_token=hrtoken ^ (corrupt_release ? 64'd1 : 64'd0);
    wire crelvalid,crelready,crelaccept,crelreject;
    wire [31:0] creladdr,crelseq,crelgen;
    wire [2:0] crelcam;
    wire crelbank;
    wire [63:0] creltoken;
    reg coop_enable=0;
    wire ctrl_input_ready;
    assign ir=ctrl_input_ready && coop_enable;
    wire cmdvalid,ctrl_busy;
    wire [31:0] cmdsrc,cmddst,cmdseq;
    reg bridge_busy=0,bridge_done=0;
    wire [1:0] out0,out1;

    // Preserve the manager's real registered response but optionally delay its
    // delivery to the control block, proving READY is not treated as success.
    integer ack_delay=0,cfgcount=0,hrcount=0;
    reg cfg_saved_accept=0,cfg_saved_reject=0,hr_saved_accept=0,hr_saved_reject=0;
    wire cfg_observed_accept=ack_delay==0 ? cfga : cfgcount==1 && cfg_saved_accept;
    wire cfg_observed_reject=ack_delay==0 ? cfge : cfgcount==1 && cfg_saved_reject;
    wire hr_observed_accept=ack_delay==0 ? hra : hrcount==1 && hr_saved_accept;
    wire hr_observed_reject=ack_delay==0 ? hre : hrcount==1 && hr_saved_reject;
    always @(posedge clk) begin
        if(!rst_n) begin cfgcount<=0;hrcount<=0;end
        else begin
            if(cfgcount>0) cfgcount<=cfgcount-1;
            if(hrcount>0) hrcount<=hrcount-1;
            if(ack_delay>0 && (cfga || cfge)) begin
                cfgcount<=ack_delay;cfg_saved_accept<=cfga;cfg_saved_reject<=cfge;
            end
            if(ack_delay>0 && (hra || hre)) begin
                hrcount<=ack_delay;hr_saved_accept<=hra;hr_saved_reject<=hre;
            end
        end
    end

    fpga_v8_coop_axi128_endpoint endpoint (
        .clk(clk),.rst_n(rst_n),
        .s_axi_awid(awid),.s_axi_awaddr(awaddr),.s_axi_awlen(awlen),.s_axi_awsize(awsize),
        .s_axi_awburst(awburst),.s_axi_awlock(1'b0),.s_axi_awcache(4'hf),.s_axi_awprot(awprot),
        .s_axi_awqos(4'h5),.s_axi_awregion(4'hb),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
        .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wlast(wlast),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
        .s_axi_bid(bid),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
        .s_axi_arid(arid),.s_axi_araddr(araddr),.s_axi_arlen(arlen),.s_axi_arsize(arsize),
        .s_axi_arburst(arburst),.s_axi_arlock(1'b0),.s_axi_arcache(4'hf),.s_axi_arprot(arprot),
        .s_axi_arqos(4'h6),.s_axi_arregion(4'hc),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
        .s_axi_rid(rid),.s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rlast(rlast),
        .s_axi_rvalid(rvalid),.s_axi_rready(rready),
        .m_axil_awaddr(ea),.m_axil_awprot(ep),.m_axil_awvalid(eav),.m_axil_awready(ear),
        .m_axil_wdata(ed),.m_axil_wstrb(es),.m_axil_wvalid(ewv),.m_axil_wready(ewr),
        .m_axil_bresp(ebp),.m_axil_bvalid(ebv),.m_axil_bready(ebr),
        .m_axil_araddr(era),.m_axil_arprot(erp),.m_axil_arvalid(erv),.m_axil_arready(erar),
        .m_axil_rdata(erd),.m_axil_rresp(errp),.m_axil_rvalid(errv),.m_axil_rready(err)
    );
    fpga_v8_coop_axil_router router (
        .clk(clk),.rst_n(rst_n),
        .s_axil_awaddr(ea),.s_axil_awprot(ep),.s_axil_awvalid(eav && ea_gate),.s_axil_awready(router_awready),
        .s_axil_wdata(ed),.s_axil_wstrb(es),.s_axil_wvalid(ewv && ew_gate),.s_axil_wready(router_wready),
        .s_axil_bresp(ebp),.s_axil_bvalid(ebv),.s_axil_bready(ebr),
        .s_axil_araddr(era),.s_axil_arprot(erp),.s_axil_arvalid(erv),.s_axil_arready(erar),
        .s_axil_rdata(erd),.s_axil_rresp(errp),.s_axil_rvalid(errv),.s_axil_rready(err),
        .m0_axil_awaddr(ca[0]),.m0_axil_awprot(cp[0]),.m0_axil_awvalid(cav[0]),.m0_axil_awready(car[0]),
        .m0_axil_wdata(cd[0]),.m0_axil_wstrb(cs[0]),.m0_axil_wvalid(cwv[0]),.m0_axil_wready(cwr[0]),
        .m0_axil_bresp(cbp[0]),.m0_axil_bvalid(cbv[0]),.m0_axil_bready(cbr[0]),
        .m0_axil_araddr(cra[0]),.m0_axil_arprot(crp[0]),.m0_axil_arvalid(crav[0]),.m0_axil_arready(crar[0]),
        .m0_axil_rdata(crd[0]),.m0_axil_rresp(crresp[0]),.m0_axil_rvalid(crv[0]),.m0_axil_rready(crr[0]),
        .m1_axil_awaddr(ca[1]),.m1_axil_awprot(cp[1]),.m1_axil_awvalid(cav[1]),.m1_axil_awready(car[1]),
        .m1_axil_wdata(cd[1]),.m1_axil_wstrb(cs[1]),.m1_axil_wvalid(cwv[1]),.m1_axil_wready(cwr[1]),
        .m1_axil_bresp(cbp[1]),.m1_axil_bvalid(cbv[1]),.m1_axil_bready(cbr[1]),
        .m1_axil_araddr(cra[1]),.m1_axil_arprot(crp[1]),.m1_axil_arvalid(crav[1]),.m1_axil_arready(crar[1]),
        .m1_axil_rdata(crd[1]),.m1_axil_rresp(crresp[1]),.m1_axil_rvalid(crv[1]),.m1_axil_rready(crr[1])
    );
    fpga_v8_capture_control_axil capture_control (
        .clk(clk),.rst_n(rst_n),
        .config_valid(cfgv),.config_ready(cfgr),.config_generation(cfggen),
        .config_accept(cfg_observed_accept),.config_reject(cfg_observed_reject),
        .epoch_start(epoch),.armed(armed),.config_ok(cfgok),.protocol_fault(fault),
        .bank0_state(bank0),.bank1_state(bank1),
        .host_valid(hv),.host_ready(hr),.host_src_addr(hs),.host_length(hl),
        .host_seq(hseq),.host_generation(hgen),.host_camera(hcam),.host_bank(hbank),.host_token(htoken),
        .host_release_valid(hrv),.host_release_ready(hrr),.host_release_camera(hrcam),.host_release_bank(hrbank),
        .host_release_seq(hrseq),.host_release_generation(hrgen),.host_release_token(hrtoken),
        .host_release_accept(hr_observed_accept),.host_release_reject(hr_observed_reject),
        .published_count(published),.failed_count(failed),.rejected_release_count(mreject),
        .s_axil_awaddr(ca[1]),.s_axil_awprot(cp[1]),.s_axil_awvalid(cav[1] && ga[1]),.s_axil_awready(cawr[1]),
        .s_axil_wdata(cd[1]),.s_axil_wstrb(cs[1]),.s_axil_wvalid(cwv[1] && gw[1]),.s_axil_wready(cwwr[1]),
        .s_axil_bresp(cbp[1]),.s_axil_bvalid(cbvalid[1]),.s_axil_bready(cbr[1] && gb[1]),
        .s_axil_araddr(cra[1]),.s_axil_arprot(crp[1]),.s_axil_arvalid(crav[1] && gra[1]),.s_axil_arready(carready[1]),
        .s_axil_rdata(crd[1]),.s_axil_rresp(crresp[1]),.s_axil_rvalid(crvalid[1]),.s_axil_rready(crr[1] && gr[1])
    );
    fpga_v8_capture_lease manager (
        .clk(clk),.rst(!rst_n),.config_valid(cfgv),.config_ready(cfgr),.config_generation(cfggen),
        .config_accept(cfga),.config_reject(cfge),.epoch_start(epoch),.armed(armed),.config_ok(cfgok),
        .engine_idle(engine_idle),.capture_bank(capture_bank),.admitted_sof(admitted_sof),
        .publish(publish),.publish_seq(publish_seq),.retired_error(retired_error),.lease_block(lease_block),
        .bank0_state(bank0),.bank1_state(bank1),.protocol_fault(fault),
        .input_valid(iv),.input_ready(ir),.input_raw_valid(raw_valid),.input_src_addr(src_addr),
        .input_length(src_len),.input_seq(src_seq),.input_generation(src_gen),.input_camera(src_cam),
        .input_bank(src_bank),.input_token(src_token),
        .release_valid(crelvalid),.release_ready(crelready),.release_camera(crelcam),.release_bank(crelbank),
        .release_seq(crelseq),.release_generation(crelgen),.release_token(creltoken),
        .release_accept(crelaccept),.release_reject(crelreject),
        .host_valid(hv),.host_ready(hr),.host_src_addr(hs),.host_length(hl),.host_seq(hseq),
        .host_generation(hgen),.host_camera(hcam),.host_bank(hbank),.host_token(htoken),
        .host_release_valid(hrv),.host_release_ready(hrr),.host_release_camera(hrcam),.host_release_bank(hrbank),
        .host_release_seq(hrseq),.host_release_generation(hrgen),.host_release_token(manager_host_release_token),
        .host_release_accept(hra),.host_release_reject(hre),
        .published_count(published),.failed_count(failed),.rejected_release_count(mreject)
    );
    fpga_v8_coop_control_axil cooperative_control (
        .core_clk(clk),.rst_n(rst_n),.input_valid(iv && coop_enable),.input_ready(ctrl_input_ready),
        .input_raw_valid(raw_valid),.input_src_addr(src_addr),.input_source_seq(src_seq),
        .input_generation(src_gen),.input_camera(src_cam),.input_camera_bank(src_bank),.input_lease_token(src_token),
        .input_claim(),.input_reject(),.cmd_valid(cmdvalid),.cmd_ready(1'b1),
        .cmd_src_addr(cmdsrc),.cmd_dst_addr(cmddst),.cmd_frame_id(cmdseq),
        .bridge_busy(bridge_busy),.bridge_done(bridge_done),.bridge_error(1'b0),.bridge_cmd_error(1'b0),
        .src_release_valid(crelvalid),.src_release_ready(crelready),.src_release_addr(creladdr),
        .src_release_seq(crelseq),.src_release_generation(crelgen),.src_release_camera(crelcam),
        .src_release_camera_bank(crelbank),.src_release_token(creltoken),
        .busy(ctrl_busy),.bank0_state(out0),.bank1_state(out1),
        .s_axil_awaddr(ca[0]),.s_axil_awprot(cp[0]),.s_axil_awvalid(cav[0] && ga[0]),.s_axil_awready(cawr[0]),
        .s_axil_wdata(cd[0]),.s_axil_wstrb(cs[0]),.s_axil_wvalid(cwv[0] && gw[0]),.s_axil_wready(cwwr[0]),
        .s_axil_bresp(cbp[0]),.s_axil_bvalid(cbvalid[0]),.s_axil_bready(cbr[0] && gb[0]),
        .s_axil_araddr(cra[0]),.s_axil_arprot(crp[0]),.s_axil_arvalid(crav[0] && gra[0]),.s_axil_arready(carready[0]),
        .s_axil_rdata(crd[0]),.s_axil_rresp(crresp[0]),.s_axil_rvalid(crvalid[0]),.s_axil_rready(crr[0] && gr[0])
    );

    reg bs=0,rs=0;
    reg [8:0] bsave;
    reg [137:0] rsave;
    reg aws[0:2],ws[0:2],ars[0:2],bcs[0:2],rcs[0:2];
    reg [34:0] awsave[0:2],arsave[0:2];
    reg [35:0] wsave[0:2];
    reg [1:0] bcsave[0:2];
    reg [33:0] rcsave[0:2];
    integer k,aw_first=0,w_first=0,router_aw_first=0,router_w_first=0;
    reg saw_aw[0:2],saw_w[0:2];
    reg cfgwaiting=0,hrwaiting=0;
    reg host_stalled=0,coop_stalled=0,router_write_owned=0,router_read_owned=0;
    reg [195:0] host_offer_save;
    reg [196:0] coop_offer_save;
    reg [31:0] router_write_addr,router_read_addr;
    reg [31:0] cfgsave;
    reg [131:0] hrsave;
    wire [31:0] watch_awaddr[0:2],watch_wdata[0:2],watch_araddr[0:2],watch_rdata[0:2];
    wire [2:0] watch_awprot[0:2],watch_arprot[0:2];
    wire [3:0] watch_wstrb[0:2];
    wire [1:0] watch_bresp[0:2],watch_rresp[0:2];
    wire wav[0:2],war[0:2],wwv[0:2],wwr[0:2],wbv[0:2],wbr[0:2],wrav[0:2],wrar[0:2],wrv[0:2],wrr[0:2];
    assign watch_awaddr[2]=ea;assign watch_awprot[2]=ep;assign wav[2]=eav;assign war[2]=ear;
    assign watch_wdata[2]=ed;assign watch_wstrb[2]=es;assign wwv[2]=ewv;assign wwr[2]=ewr;
    assign watch_bresp[2]=ebp;assign wbv[2]=ebv;assign wbr[2]=ebr;
    assign watch_araddr[2]=era;assign watch_arprot[2]=erp;assign wrav[2]=erv;assign wrar[2]=erar;
    assign watch_rdata[2]=erd;assign watch_rresp[2]=errp;assign wrv[2]=errv;assign wrr[2]=err;
    generate for(g=0;g<2;g=g+1) begin: monitors
        assign watch_awaddr[g]=ca[g];assign watch_awprot[g]=cp[g];assign wav[g]=cav[g];assign war[g]=car[g];
        assign watch_wdata[g]=cd[g];assign watch_wstrb[g]=cs[g];assign wwv[g]=cwv[g];assign wwr[g]=cwr[g];
        assign watch_bresp[g]=cbp[g];assign wbv[g]=cbvalid[g];assign wbr[g]=cbr[g] && gb[g];
        assign watch_araddr[g]=cra[g];assign watch_arprot[g]=crp[g];assign wrav[g]=crav[g];assign wrar[g]=crar[g];
        assign watch_rdata[g]=crd[g];assign watch_rresp[g]=crresp[g];assign wrv[g]=crvalid[g];assign wrr[g]=crr[g] && gr[g];
    end endgenerate
    always @(negedge clk) cycle=cycle+1;
    always @(posedge clk) begin
        if(cycle>100000) $fatal(1,"watchdog op=%0d",op);
        if(cycle>1) begin
            if((^{awready,wready,bid,bresp,bvalid,arready,rid,rdata,rresp,rlast,rvalid,
                cfgv,cfgr,cfggen,cfga,cfge,epoch,armed,cfgok,fault,lease_block,bank0,bank1,
                iv,ir,raw_valid,src_addr,src_len,src_seq,src_gen,src_cam,src_bank,src_token,
                hv,hr,hs,hl,hseq,hgen,hcam,hbank,htoken,hrv,hrr,hrcam,hrbank,hrseq,hrgen,hrtoken,hra,hre,
                crelvalid,crelready,creladdr,crelseq,crelgen,crelcam,crelbank,creltoken,crelaccept,crelreject,
                manager_host_release_token,published,failed,mreject,cmdvalid,cmdsrc,cmddst,cmdseq,out0,out1,ctrl_busy})===1'bx) $fatal(1,"X/Z output");
            if((^{cawr[0],cawr[1],cwwr[0],cwwr[1],cbvalid[0],cbvalid[1],carready[0],carready[1],
                crvalid[0],crvalid[1],cbr[0],cbr[1],crr[0],crr[1],router_awready,router_wready})===1'bx) $fatal(1,"X/Z ungated child output");
            for(k=0;k<3;k=k+1) begin
                if((^{watch_awaddr[k],watch_awprot[k],wav[k],war[k],watch_wdata[k],watch_wstrb[k],wwv[k],wwr[k],
                    watch_bresp[k],wbv[k],wbr[k],watch_araddr[k],watch_arprot[k],wrav[k],wrar[k],
                    watch_rdata[k],watch_rresp[k],wrv[k],wrr[k]})===1'bx) $fatal(1,"X/Z local %0d",k);
            end
        end
        if(rst_n) begin
            if(host_stalled && (!hv || {hs,hl,hseq,hgen,hcam,hbank,htoken}!==host_offer_save)) $fatal(1,"host offer changed before claim");
            if(coop_stalled && (!iv || {raw_valid,src_addr,src_len,src_seq,src_gen,src_cam,src_bank,src_token}!==coop_offer_save)) $fatal(1,"cooperative offer changed before claim");
            if(eav && ear) begin
                if(router_write_owned) $fatal(1,"router accepted AW before B consumption");
                router_write_owned=1;router_write_addr=ea;
            end
            if(erv && erar) begin
                if(router_read_owned) $fatal(1,"router accepted AR before R consumption");
                router_read_owned=1;router_read_addr=era;
            end
            if((cav[0] && cav[1]) || (cwv[0] && cwv[1]) || (crav[0] && crav[1])) $fatal(1,"both child routes active");
            for(k=0;k<2;k=k+1) begin
                if((cav[k] || cwv[k]) && (!router_write_owned || (router_write_addr>=32'h100)!=k)) $fatal(1,"wrong child write route");
                if(crav[k] && (!router_read_owned || (router_read_addr>=32'h100)!=k)) $fatal(1,"wrong child read route");
            end
            if(ebv && ebr) router_write_owned=0;
            if(errv && err) router_read_owned=0;
            if(bs && (!bvalid || {bid,bresp}!==bsave)) $fatal(1,"full B unstable");
            if(rs && (!rvalid || {rid,rdata,rresp,rlast}!==rsave)) $fatal(1,"full R unstable");
            for(k=0;k<3;k=k+1) begin
                if(aws[k] && (!wav[k] || {watch_awaddr[k],watch_awprot[k]}!==awsave[k])) $fatal(1,"AW unstable %0d",k);
                if(ws[k] && (!wwv[k] || {watch_wdata[k],watch_wstrb[k]}!==wsave[k])) $fatal(1,"W unstable %0d",k);
                if(ars[k] && (!wrav[k] || {watch_araddr[k],watch_arprot[k]}!==arsave[k])) $fatal(1,"AR unstable %0d",k);
                if(bcs[k] && (!wbv[k] || watch_bresp[k]!==bcsave[k])) $fatal(1,"B unstable %0d",k);
                if(rcs[k] && (!wrv[k] || {watch_rdata[k],watch_rresp[k]}!==rcsave[k])) $fatal(1,"R unstable %0d",k);
                if(wav[k] && war[k] && !saw_w[k] && !(wwv[k] && wwr[k])) begin
                    if(k==2) router_aw_first=router_aw_first+1;else aw_first=aw_first+1;
                end
                if(wwv[k] && wwr[k] && !saw_aw[k] && !(wav[k] && war[k])) begin
                    if(k==2) router_w_first=router_w_first+1;else w_first=w_first+1;
                end
                if(wav[k] && war[k]) saw_aw[k]=1;
                if(wwv[k] && wwr[k]) saw_w[k]=1;
                if(wbv[k] && wbr[k]) begin saw_aw[k]=0;saw_w[k]=0;end
                if(wav[k] && war[k]) $fdisplay(trace,"%0d L%0dAW %x %x",op,k,watch_awaddr[k],watch_awprot[k]);
                if(wwv[k] && wwr[k]) $fdisplay(trace,"%0d L%0dW %x %x",op,k,watch_wdata[k],watch_wstrb[k]);
                if(wbv[k] && wbr[k]) $fdisplay(trace,"%0d L%0dB %x",op,k,watch_bresp[k]);
                if(wrav[k] && wrar[k]) $fdisplay(trace,"%0d L%0dAR %x %x",op,k,watch_araddr[k],watch_arprot[k]);
                if(wrv[k] && wrr[k]) $fdisplay(trace,"%0d L%0dR %x %x",op,k,watch_rdata[k],watch_rresp[k]);
            end
            if(cfgwaiting && cbvalid[1] && !cfg_observed_accept && !cfg_observed_reject) $fatal(1,"ARM B guessed from handshake");
            if(hrwaiting && cbvalid[1] && !hr_observed_accept && !hr_observed_reject) $fatal(1,"RAWACK B guessed from handshake");
            if(cfgv && cfgr) begin
                cfgwaiting=1;cfgsave=cfggen;
                $fdisplay(trace,"%0d CONFIG %x",op,cfggen);
            end
            if(cfg_observed_accept || cfg_observed_reject) begin
                cfgwaiting=0;$fdisplay(trace,"%0d CONFIG_OBS %x %x",op,cfg_observed_accept,cfg_observed_reject);
            end
            if(cfga || cfge) $fdisplay(trace,"%0d CONFIG_ACK %x %x",op,cfga,cfge);
            if(hrv && hrr) begin
                hrwaiting=1;hrsave={hrcam,hrbank,hrseq,hrgen,hrtoken};
                $fdisplay(trace,"%0d HOST_RELEASE %x %x %x %x %x",op,hrcam,hrbank,hrseq,hrgen,hrtoken);
                $fdisplay(trace,"%0d MANAGER_HOST_RELEASE %x %x %x %x %x",op,hrcam,hrbank,hrseq,hrgen,manager_host_release_token);
            end
            if(hr_observed_accept || hr_observed_reject) begin
                hrwaiting=0;$fdisplay(trace,"%0d RELEASE_OBS %x %x",op,hr_observed_accept,hr_observed_reject);
            end
            if(hra || hre) $fdisplay(trace,"%0d RELEASE_ACK %x %x",op,hra,hre);
            if(hr && hv) $fdisplay(trace,"%0d HOST_CLAIM %x %x %x %x %x %x %x",op,hbank,hseq,hgen,hl,hs,hcam,htoken);
            if(iv && ir) $fdisplay(trace,"%0d COOP_CLAIM %x %x %x %x %x %x %x",op,src_bank,src_seq,src_gen,src_len,src_addr,src_cam,src_token);
            if(cmdvalid) $fdisplay(trace,"%0d CMD %x %x %x",op,cmdsrc,cmddst,cmdseq);
            if(crelvalid && crelready) $fdisplay(trace,"%0d COOP_RELEASE %x %x %x %x %x",op,crelcam,crelbank,crelseq,crelgen,creltoken);
            if(sof_attempt) $fdisplay(trace,"%0d SOF %x %x %x",op,capture_bank,admitted_sof,lease_block);
            if(publish) $fdisplay(trace,"%0d PUBLISH %x",op,publish_seq);
            if(retired_error) $fdisplay(trace,"%0d RETIRED_ERROR",op);
            if(awvalid && awready) $fdisplay(trace,"%0d AW %x %x %x %x %x %x",op,awid,awaddr,awlen,awsize,awburst,awprot);
            if(wvalid && wready) $fdisplay(trace,"%0d W %x %x %x",op,wdata,wstrb,wlast);
            if(bvalid && bready) $fdisplay(trace,"%0d B %x %x",op,bid,bresp);
            if(arvalid && arready) $fdisplay(trace,"%0d AR %x %x %x %x %x %x",op,arid,araddr,arlen,arsize,arburst,arprot);
            if(rvalid && rready) $fdisplay(trace,"%0d R %x %x %x %x",op,rid,rdata,rresp,rlast);
        end else begin cfgwaiting=0;hrwaiting=0;router_write_owned=0;router_read_owned=0;end
        host_stalled=rst_n && hv && !hr;host_offer_save={hs,hl,hseq,hgen,hcam,hbank,htoken};
        coop_stalled=rst_n && iv && !ir;coop_offer_save={raw_valid,src_addr,src_len,src_seq,src_gen,src_cam,src_bank,src_token};
        bs=rst_n && bvalid && !bready;bsave={bid,bresp};
        rs=rst_n && rvalid && !rready;rsave={rid,rdata,rresp,rlast};
        for(k=0;k<3;k=k+1) begin
            aws[k]=rst_n && wav[k] && !war[k];awsave[k]={watch_awaddr[k],watch_awprot[k]};
            ws[k]=rst_n && wwv[k] && !wwr[k];wsave[k]={watch_wdata[k],watch_wstrb[k]};
            ars[k]=rst_n && wrav[k] && !wrar[k];arsave[k]={watch_araddr[k],watch_arprot[k]};
            bcs[k]=rst_n && wbv[k] && !wbr[k];bcsave[k]=watch_bresp[k];
            rcs[k]=rst_n && wrv[k] && !wrr[k];rcsave[k]={watch_rdata[k],watch_rresp[k]};
            if(!rst_n) begin saw_aw[k]=0;saw_w[k]=0;end
        end
    end

    task tick(input integer n);repeat(n) @(negedge clk);endtask
    task reset_all;
        begin
            @(negedge clk);rst_n=0;awvalid=0;wvalid=0;arvalid=0;bready=0;rready=0;
            sof_attempt=0;publish=0;retired_error=0;engine_idle=1;capture_bank=0;
            coop_enable=0;bridge_busy=0;bridge_done=0;ack_delay=0;hold_capture_b=0;corrupt_release=0;
            tick(5);rst_n=1;tick(12);$fdisplay(trace,"%0d RESET",op);
        end
    endtask
    function [127:0] payload(input [31:0] low,input integer beat);
        reg [31:0] x,y,z;
        begin
            x=32'hd193672b ^ low ^ (beat*32'h9e3779b9);
            x=x^(x<<13);x=x^(x>>17);x=x^(x<<5);
            y=x^(x<<13);y=y^(y>>17);y=y^(y<<5);
            z=y^(y<<13);z=z^(z>>17);z=z^(z<<5);
            payload={x,y,z,low+beat};
        end
    endfunction
    task send_aw(input [31:0] addr,input integer len,size,burst,id,prot,delay_n);
        begin
            tick(delay_n);awaddr=addr;awlen=len;awsize=size;awburst=burst;awid=id;awprot=prot;awvalid=1;
            do @(posedge clk);while(!awready);
            @(negedge clk);awvalid=0;awaddr=32'hdeadbeef;awid=7'h7f;awprot=7;
        end
    endtask
    task send_w(input integer len,input [31:0] low,input [15:0] strb,input integer delay_n,lastmode);
        integer i;
        begin
            tick(delay_n);
            for(i=0;i<=len;i=i+1) begin
                wdata=payload(low,i);wstrb=strb;wlast=lastmode==0 ? i==len : i==0;wvalid=1;
                do @(posedge clk);while(!wready);
                @(negedge clk);wvalid=0;
            end
            wdata=128'hfeedface;wstrb=0;wlast=0;
        end
    endtask
    task take_b(input integer hold_n);
        begin wait(bvalid);tick(hold_n);bready=1;do @(posedge clk);while(!bvalid);@(negedge clk);bready=0;end
    endtask
    task write_one(input [31:0] addr,input integer len,size,burst,id,input [31:0] low,
                   input [15:0] strb,input integer order_n,prot,hold_n,lastmode);
        fork
            send_aw(addr,len,size,burst,id,prot,order_n==1 ? 7 : 0);
            send_w(len,low,strb,order_n==2 ? 7 : 0,lastmode);
            take_b(hold_n);
        join
    endtask
    task send_ar(input [31:0] addr,input integer len,size,burst,id,prot);
        begin
            araddr=addr;arlen=len;arsize=size;arburst=burst;arid=id;arprot=prot;arvalid=1;
            do @(posedge clk);while(!arready);
            @(negedge clk);arvalid=0;araddr=32'hbeeff00d;arid=7'h7f;arprot=7;
        end
    endtask
    task take_r(input integer len,hold_n);
        integer i;
        begin for(i=0;i<=len;i=i+1) begin
            wait(rvalid);tick(hold_n+i%3);rready=1;do @(posedge clk);while(!rvalid);@(negedge clk);rready=0;
        end end
    endtask
    task read_one(input [31:0] addr,input integer len,size,burst,id,prot,hold_n);
        fork send_ar(addr,len,size,burst,id,prot);take_r(len,hold_n);join
    endtask
    initial begin
        trace=$fopen("actual.trace","w");stim=$fopen("stimulus.txt","r");
        if(!trace || !stim) $fatal(1,"files");
        for(k=0;k<3;k=k+1) begin aws[k]=0;ws[k]=0;ars[k]=0;bcs[k]=0;rcs[k]=0;saw_aw[k]=0;saw_w[k]=0;end
        while(!$feof(stim)) begin
            rc=$fscanf(stim,"%d %h %h %h %h %h %h %h %h %h %h %h %h\n",code,
                a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10],a[11]);
            if(rc!=13) $fatal(1,"stimulus");
            @(negedge clk);op=op+1;
            case(code)
                0: reset_all();
                1: write_one(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10]);
                2: read_one(a[0],a[1],a[2],a[3],a[4],a[5],a[6]);
                3: begin
                    // An attempted SOF on ARM's exact dispatch edge must be
                    // blocked; inject only actual admitted events to manager.
                    fork
                        write_one(32'h40010440,0,4,1,a[0],1,16'hffff,a[1],3,23,0);
                        begin wait(cfgv);@(negedge clk);sof_attempt=1;@(posedge clk);@(negedge clk);sof_attempt=0;end
                    join
                end
                4: begin capture_bank=a[0];sof_attempt=1;if(!lease_block) engine_idle=0;tick(1);sof_attempt=0;end
                5: begin publish_seq=a[0];publish=1;engine_idle=1;tick(1);publish=0;end
                6: begin coop_enable=a[0];tick(20);end
                7: begin bridge_busy=0;bridge_done=1;tick(1);bridge_done=0;tick(20);end
                8: engine_idle=a[0];
                9: begin
                    // Write to capture while read targets cooperative, or vice
                    // versa. Different routes must never exchange ownership.
                    fork
                        write_one(a[0],0,4,1,a[4],a[1],16'hffff,1,2,27,0);
                        read_one(a[2],0,4,1,a[5],5,31);
                    join
                end
                10: begin
                    // Leave actual manager acceptance unobserved for 80 cycles.
                    ack_delay=80;
                    fork
                        write_one(a[0],0,4,1,a[1],1,16'hffff,2,6,17,0);
                        begin
                            if(a[0]==32'h40010440) wait(cfgv);else wait(hrv);
                            tick(7);read_one(32'h40010410,0,4,1,a[2],4,25);
                        end
                    join
                    tick(5);ack_delay=0;
                end
                11: begin
                    // Second transaction changes route while first B is held.
                    fork
                        begin send_aw(a[0],0,4,1,a[4],3,0);send_aw(a[1],0,4,0,a[4]+1,7,0);end
                        begin send_w(0,a[2],16'hffff,0,0);send_w(0,a[3],16'hffff,0,0);end
                        begin take_b(41);take_b(37);end
                    join
                end
                12: begin retired_error=1;engine_idle=1;tick(1);retired_error=0;end
                13: begin
                    // Full held R must remain a snapshot when another bank is
                    // published and the manager's live host offer changes.
                    send_ar(a[0],0,4,1,a[1],2);wait(rvalid);tick(7);
                    publish_seq=a[2];publish=1;engine_idle=1;tick(1);publish=0;tick(27);take_r(0,19);
                end
                14: begin
                    hold_capture_b=1;
                    fork
                        send_aw(32'h40010440,0,4,1,7'h70,1,0);
                        send_w(0,1,16'hffff,0,0);
                    join
                    wait(cbvalid[1]);tick(29);reset_all();
                end
                15: begin
                    // Deliberate interconnect identity corruption: the actual
                    // manager rejects, and capture control must preserve its
                    // bound descriptor until a later accepted release.
                    corrupt_release=1;
                    write_one(32'h40010540,0,4,1,a[0],1,16'hffff,1,7,31,0);
                    corrupt_release=0;
                end
                default: $fatal(1,"opcode");
            endcase
            tick(25);
            $fdisplay(trace,"%0d STATE %x %x %x %x %x %x %x %x %x",op,
                bank0,bank1,armed,fault,hv,hbank,out0,out1,ctrl_busy);
        end
        if(!aw_first || !w_first || !router_aw_first || !router_w_first) $fatal(1,"missing AW/W ordering coverage");
        tick(5);$fclose(trace);$fclose(stim);
        $display("CAPTURE_ENDPOINT_PASS ops=%0d cycles=%0d child_AW_first=%0d child_W_first=%0d router_AW_first=%0d router_W_first=%0d",op,cycle,aw_first,w_first,router_aw_first,router_w_first);$finish;
    end
    always @(negedge clk) if(rst_n && cmdvalid) bridge_busy=1;
endmodule
