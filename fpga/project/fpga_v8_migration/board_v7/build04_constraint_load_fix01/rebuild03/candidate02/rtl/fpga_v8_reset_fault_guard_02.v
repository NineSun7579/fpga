// Admission guard. Faults require FPGA reconfiguration, not a local reset.
module fpga_v8_reset_fault_guard_02 #(
    parameter integer ALIVE_LIMIT=256,
    parameter integer QUALIFY_CYCLES=32
)(
    input wire free_clk, button_rst_n, perst_n,
    input wire axi_clk, axi_rst, ddr_init_done, startup_idle_axi,
    input wire pcie_clk, pcie_rst, smlh_link_up, rdlh_link_up, startup_idle_pcie,
    output reg fault=0,
    output reg runtime_active=0,
    output reg reconfiguration_required=0,
    output wire admit_axi, admit_pcie, fault_axi, fault_pcie
);
    wire axi_reset=axi_rst || !button_rst_n;
    wire pcie_reset=pcie_rst || !button_rst_n;
    reg [3:0] ah=0, ph=0;
    reg [1:0] aa=0, pa=0;
    always @(posedge axi_clk or posedge axi_reset)
        if (axi_reset) begin ah<=0; aa<=0; end
        else begin ah<=ah+1'b1; aa<={aa[0],ddr_init_done && startup_idle_axi}; end
    always @(posedge pcie_clk or posedge pcie_reset)
        if (pcie_reset) begin ph<=0; pa<=0; end
        else begin ph<=ph+1'b1; pa<={pa[0],perst_n && smlh_link_up && rdlh_link_up && startup_idle_pcie}; end

    wire health_n=button_rst_n && perst_n && !pcie_rst && !axi_rst &&
                  ddr_init_done && smlh_link_up && rdlh_link_up;
    // A single asynchronous reset pin captures a pulse even between clock edges.
    // At the next free_clk edge the supervisor sees the old zero before this FF
    // rearms. No event signal is used as a clock, and no state-dependent async
    // set/clear priority is required.
    (* syn_preserve=1, syn_allow_retiming=0 *) reg health_seen=0;
    (* syn_preserve=1, syn_allow_retiming=0 *) reg button_seen=0;
    always @(posedge free_clk or negedge health_n)
        if (!health_n) health_seen<=0; else health_seen<=1;
    always @(posedge free_clk or negedge button_rst_n)
        if (!button_rst_n) button_seen<=0; else button_seen<=1;

    (* syn_preserve=1, syn_allow_retiming=0 *) reg [1:0] as=0, ps=0, aks=0, pks=0;
    reg alast=0, plast=0;
    localparam AGE_WIDTH=$clog2(ALIVE_LIMIT+1);
    localparam QUAL_WIDTH=$clog2(QUALIFY_CYCLES+1);
    reg [AGE_WIDTH-1:0] aage=ALIVE_LIMIT, page=ALIVE_LIMIT;
    reg [QUAL_WIDTH-1:0] qualified=0;
    // All persistent state uses free_clk only. A runtime button is a fault;
    // it cannot clear authority or silently start another session.
    always @(posedge free_clk) begin
        as<={as[0],ah[3]}; ps<={ps[0],ph[3]};
        aks<={aks[0],aa[1]}; pks<={pks[0],pa[1]};
        alast<=as[1]; plast<=ps[1];
        if (as[1]!=alast) aage<=0; else if(aage<ALIVE_LIMIT) aage<=aage+1'b1;
        if (ps[1]!=plast) page<=0; else if(page<ALIVE_LIMIT) page<=page+1'b1;
        if (runtime_active) begin
            if (!health_seen || !health_n || aage>=ALIVE_LIMIT || page>=ALIVE_LIMIT)
                fault<=1;
            if (!button_seen || !button_rst_n) reconfiguration_required<=1;
        end else begin
            if (health_seen && health_n && aks[1] && pks[1] &&
                aage<ALIVE_LIMIT && page<ALIVE_LIMIT && !fault) begin
                if (qualified==QUALIFY_CYCLES-1) runtime_active<=1;
                else qualified<=qualified+1'b1;
            end else qualified<=0;
        end
    end
    wire close_admission=!health_n || !health_seen || fault ||
                         reconfiguration_required || !runtime_active;
    (* syn_preserve=1, syn_allow_retiming=0 *) reg [1:0] axpermit=0, pcpermit=0;
    (* syn_preserve=1, syn_allow_retiming=0 *) reg [1:0] axfault=0, pcfault=0;
    always @(posedge axi_clk or posedge close_admission)
        if(close_admission) axpermit<=0; else axpermit<={axpermit[0],1'b1};
    always @(posedge pcie_clk or posedge close_admission)
        if(close_admission) pcpermit<=0; else pcpermit<={pcpermit[0],1'b1};
    always @(posedge axi_clk) axfault<={axfault[0],fault || reconfiguration_required};
    always @(posedge pcie_clk) pcfault<={pcfault[0],fault || reconfiguration_required};
    assign admit_axi=axpermit[1] && !close_admission;
    assign admit_pcie=pcpermit[1] && !close_admission;
    assign fault_axi=axfault[1];
    assign fault_pcie=pcfault[1];
endmodule
