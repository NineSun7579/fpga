// Admission isolation only. No reset output and no transaction-retirement receipt.
module fpga_v8_reset_fault_guard #(
    parameter integer ALIVE_LIMIT=256,
    parameter integer QUALIFY_CYCLES=32
)(
    input wire free_clk, button_rst_n, perst_n,
    input wire axi_clk, axi_rst, ddr_init_done, startup_idle_axi,
    input wire pcie_clk, pcie_rst, smlh_link_up, rdlh_link_up, startup_idle_pcie,
    output reg fault=0,
    output reg runtime_active=0,
    output reg reconfiguration_required=0,
    output wire admit_axi, admit_pcie,
    output wire fault_axi, fault_pcie
);
    // Heartbeats deliberately divided before CDC. Missing/aliased edges fail closed.
    reg [3:0] ah=0, ph=0;
    reg [1:0] aa=0, pa=0;
    always @(posedge axi_clk or posedge axi_rst or negedge button_rst_n)
        if (!button_rst_n || axi_rst) begin ah<=0; aa<=0; end
        else begin ah<=ah+1'b1; aa<={aa[0],ddr_init_done && startup_idle_axi}; end
    always @(posedge pcie_clk or posedge pcie_rst or negedge button_rst_n)
        if (!button_rst_n || pcie_rst) begin ph<=0; pa<=0; end
        else begin ph<=ph+1'b1; pa<={pa[0],perst_n && smlh_link_up && rdlh_link_up && startup_idle_pcie}; end
    (* ASYNC_REG="TRUE" *) reg [1:0] as=0, ps=0, aks=0, pks=0;
    reg alast=0, plast=0;
    localparam AGE_WIDTH=$clog2(ALIVE_LIMIT+1);
    localparam QUAL_WIDTH=$clog2(QUALIFY_CYCLES+1);
    reg [AGE_WIDTH-1:0] aage=ALIVE_LIMIT, page=ALIVE_LIMIT;
    reg [QUAL_WIDTH-1:0] qualified=0;
    wire healthy=perst_n && !pcie_rst && !axi_rst && ddr_init_done &&
                 smlh_link_up && rdlh_link_up;
    wire bad_event=runtime_active && !healthy;
    // Asynchronous assertion captures short actual reset/loss pulses. Integration
    // requires reset/CDC timing signoff; simulation is not a PDS implementation check.
    always @(posedge free_clk or posedge bad_event or negedge button_rst_n)
        if (!button_rst_n) fault<=0;
        else if (bad_event) fault<=1;
        else if (runtime_active && (aage>=ALIVE_LIMIT || page>=ALIVE_LIMIT)) fault<=1;

    // A runtime button clears fault but is NOT a certified recovery provider.
    // Conservatively block the configured image until a new configuration.
    always @(posedge free_clk or negedge button_rst_n)
        if (!button_rst_n) begin
            if (runtime_active || fault) reconfiguration_required<=1;
        end else if (reconfiguration_required) reconfiguration_required<=1;

    always @(posedge free_clk or negedge button_rst_n) begin
        if (!button_rst_n) begin
            as<=0; ps<=0; aks<=0; pks<=0; alast<=0; plast<=0;
            aage<=ALIVE_LIMIT; page<=ALIVE_LIMIT; qualified<=0; runtime_active<=0;
        end else begin
            as<={as[0],ah[3]}; ps<={ps[0],ph[3]};
            aks<={aks[0],aa[1]}; pks<={pks[0],pa[1]};
            alast<=as[1]; plast<=ps[1];
            if (as[1]!=alast) aage<=0; else if(aage<ALIVE_LIMIT) aage<=aage+1;
            if (ps[1]!=plast) page<=0; else if(page<ALIVE_LIMIT) page<=page+1;
            if (!runtime_active) begin
                if (healthy && aks[1] && pks[1] && aage<ALIVE_LIMIT && page<ALIVE_LIMIT &&
                    !fault && !reconfiguration_required) begin
                    if (qualified==QUALIFY_CYCLES-1) runtime_active<=1;
                    else qualified<=qualified+1;
                end else qualified<=0;
            end
        end
    end
    wire close_admission=!button_rst_n || !healthy || fault || reconfiguration_required || !runtime_active;
    (* ASYNC_REG="TRUE" *) reg [1:0] axpermit=0, pcpermit=0;
    (* ASYNC_REG="TRUE" *) reg [1:0] axfault=0, pcfault=0;
    // Permit closes asynchronously, opens only after two local clock samples.
    // Domain resets do not clear the persistent fault/readback path.
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
