module conv11_weight #(
    parameter AXI_DATA_WIDTH = 32,
              AXI_ADDR_WIDTH = 32,
    parameter CHA_PAR_IN = 16,                           //����ͨ�����ж�
              CHA_PAR_OUT = 8,                           //���ͨ�����ж�
              CHA_IMG_IN = 128,                          //�����IMG�����ͨ����
              CHA_IMG_OUT = 256,                         //�����IMG�����ͨ����
              INT = 8,                                   //ÿ������λ��
              //������DMA����weight�����ֽ��� ����bias   ===�� ci*co*9 + co * 16�ֽ�
              //ci*co*9��weight���ֽ��� һ��bias��128λ��Ҳ����16�ֽ��������Լ���co*16����biasֻ��32λ����Ч��  
              WEIGHT_SUM = CHA_IMG_IN * CHA_IMG_OUT * 9 + CHA_IMG_OUT * 16,  //ÿ��ȡһС����weight
              WEIGHT_SUM_WIDTH = $clog2(WEIGHT_SUM),
              //һ��weight����ֽ���
              WEIGHT_LEN = CHA_IMG_IN * CHA_IMG_OUT,
              WEIGHT33_LEN = CHA_IMG_IN * CHA_IMG_OUT,
              WEIGHT_LEN_WIDTH = $clog2(WEIGHT_LEN),
              //RAM-weight
              DATA_WIDTH = CHA_PAR_IN * INT,             //���ݴ���λ��    ���벢�ж� * INT8
              DATA_DEPTH = CHA_PAR_OUT,                  //�������  ������ weight�ĸ���/ÿһ�е���ȡ�ĸ���
              //BIAS
              BIAS_NUM = 2 ,                             //һ��ƴ�ӵ�bias����
              BISA_CNT_NUM = CHA_PAR_OUT / BIAS_NUM,     //bias�ļ�����   ÿ�μ���bias
              BIAS_LEN = (CHA_IMG_OUT / BIAS_NUM * CHA_PAR_IN) ,              //bias_len�ĳ��Ȱ���biasȫ��ͨ�������ֽ���
              BIAS_LEN_WIDTH = $clog2(BIAS_LEN),
              //RAM-bias
              BIAS_WIDTH = 32 * BIAS_NUM,                         //ƫ�õ�λ��
              BIAS_DEPTH = CHA_IMG_OUT / BIAS_NUM,                //����ж��ٸ�ƫ��  Ҳ�������ͨ������
              //����������
              MAX_IN_COL = 320,                          //�����IMG���������
              COL_WIDTH = $clog2(MAX_IN_COL),
              MAX_IN_ROW = 320,                          //�����IMG���������
              ROW_WIDTH = $clog2(MAX_IN_ROW),
              MAX_IN_CALULATE_NUM = (CHA_IMG_IN / CHA_PAR_IN),                //����ͨ���������=����ͨ����/���벢�ж� 
              MAX_OUT_CALULATE_NUM = (CHA_IMG_OUT / CHA_PAR_OUT),             //���ͨ���������=���ͨ����/������ж� 
              OUT_CALULATE_CNT_WIDTH = $clog2(MAX_OUT_CALULATE_NUM),
              CALULATE_NUM = MAX_IN_CALULATE_NUM * MAX_OUT_CALULATE_NUM,      //��ͨ���������=����ͨ��������� * ���ͨ��������� 
              CALULATE_CNT_WIDTH = $clog2(CALULATE_NUM),


              READ_DELAY = 1,
    //дѭ��RAM������
    parameter RAM_CNT = 2,                                 //�̶�9��ram ÿ��ram�洢9������һ��
              RAM_CNT_WIDTH = $clog2(RAM_CNT+1)
)
(
    input          clk         ,
    input          rst         ,

    input          start       ,
    input          type        ,
    input          stride      ,

    input  [AXI_DATA_WIDTH-1 : 0] base_addr,              //д�ڴ����ʼ����ַ
    input  [WEIGHT_SUM_WIDTH : 0] weight_sum,              //������DMA����weight�����ֽ��� ����bias   ===�� ci*co*9 + co * 16�ֽ�
    input  [WEIGHT_LEN_WIDTH : 0] weight_len,

    input  [ROW_WIDTH : 0]         row_num          ,

    input  [CALULATE_CNT_WIDTH : 0]      calculate_num         ,
    input  [OUT_CALULATE_CNT_WIDTH : 0]  calculate_cout_num    ,
    

    input  [DATA_WIDTH-1 : 0] s_data    ,
    input                     s_valid   ,
    input                     s_last    ,
    output                    s_ready   ,

    

    output reg [DATA_WIDTH-1 : 0] m_data_4  ,
    output                        m_valid   ,
    output                        m_last    ,
    input                         m_req     ,


    output reg [BIAS_WIDTH-1 : 0]  bias        ,
    output reg                     bias_valid  ,
    output reg                     bias_last   ,
    input                          bias_req    ,

    output [AXI_ADDR_WIDTH-1 : 0]  cmd_addr    ,
    output [AXI_DATA_WIDTH-1 : 0]  cmd_len     ,
    output                         cmd_valid   ,
    input                          cmd_ready   ,

    input          calculate_end                //��������ź�4
    
);

    //������ȡ�ı��� MAX_MUL*CHA_PAR_OUT ���ܳ���FIFO�����
    localparam MAX_MUL = 16;
    reg [CALULATE_CNT_WIDTH : 0] multiple;
    always @(posedge clk) begin
        if(calculate_num > MAX_MUL) begin
            multiple <= MAX_MUL;
        end 
        else begin
            multiple <= calculate_num;
        end
    end


    wire [RAM_CNT-1 : 0] almost_full, almost_empty, full, empty;
    wire almost_full_now, full_now;

    //״̬��
    localparam IDLE = 4'b0001, WADDR = 4'b0010, WDATA = 4'b0100, W_WAIT = 4'b1000;
    reg [3 : 0] state, next_state;
    always @(posedge clk) begin
        if(rst) begin
            state <= IDLE;
        end
        else begin
            state <= next_state;
        end
    end

    always @(*) begin
        case(state)
            IDLE:begin
                if(start) begin
                    next_state = WADDR;
                end
                else begin
                    next_state = IDLE;
                end
            end
            WADDR:begin                                       //����DMA��ַ��������
                if(cmd_valid & cmd_ready) begin
                    next_state = WDATA;
                end
                else begin
                    next_state = WADDR;
                end
            end
            WDATA:begin                                        //��DMA������ݳ�����д�뵱ǰģ��
                if(s_last & s_valid & s_ready) begin                 ////////////////////////////////////////���ﲻһ�� ////////////////////////////////////
                    next_state = W_WAIT;
                end
                else begin
                    next_state = WDATA;
                end
            end
            W_WAIT:begin
                if(row_cnt == row_num) begin
                    next_state = IDLE;
                end
                else if(~almost_full_now) begin
                    next_state = WADDR;
                end
                else begin
                    next_state = W_WAIT;
                end
            end
            default:begin
                next_state = IDLE;
            end
        endcase
    end


////////////////////////////////////////////�������/////////////////////////////////////////
    reg [CALULATE_CNT_WIDTH : 0] calculate_cnt;
    always @(posedge clk) begin
        if(rst) begin
            calculate_cnt <= 0;
        end
        else if(w_ram_cnt == 0) begin
            calculate_cnt <= 0;
        end
        else if((state == WDATA) && (next_state == W_WAIT)) begin
            if(calculate_cnt >= calculate_num - multiple) begin
                calculate_cnt <= 0;
            end
            else begin
                calculate_cnt <= calculate_cnt + multiple;
            end
        end
    end

 

    reg [ROW_WIDTH : 0] row_cnt;
    always @(posedge clk) begin
        if(rst) begin
            row_cnt <= 0;
        end
        else if(w_ram_cnt == 0) begin
            row_cnt <= 0;
        end
        else if(((state == WDATA) && (next_state == W_WAIT)) && (calculate_cnt >= calculate_num - multiple)) begin
            row_cnt <= row_cnt + 1;
        end
    end


    ////////////////////////////////////////////CMD////////////////////////////////////////////////
    reg [AXI_ADDR_WIDTH-1 : 0] end_addr;
    always @(posedge clk) begin
        if(state == IDLE) begin
            end_addr <= base_addr + weight_sum; // ������ʱԤ�ȼ��㲢����
        end
    end


    localparam WEIGHT_STRIDE_11 = CHA_PAR_IN * CHA_PAR_OUT ;            //conv11��ÿ�δ�DMAR��ȡ���ֽ���

    reg [AXI_ADDR_WIDTH-1 : 0] type_stride;
    always @(posedge clk) begin
        type_stride <= WEIGHT_STRIDE_11 * multiple;
    end

    reg [AXI_ADDR_WIDTH-1 : 0] weight_stride;
    always @(posedge clk) begin
        if(w_ram_cnt == 0) begin
            weight_stride <= weight_len;
        end
        else if(end_addr - data_addr >= type_stride) begin
            weight_stride <= type_stride;
        end
        else begin
            weight_stride <= end_addr - data_addr;
        end
    end
    assign cmd_len = weight_stride;


    //�ڴ��ȡ��ַ����
    reg [AXI_ADDR_WIDTH-1 : 0] data_addr;
    always @(posedge clk) begin
        if(state == IDLE) begin
            data_addr <= base_addr;
        end
        else if(cmd_valid & cmd_ready) begin
            if(data_addr + weight_stride == end_addr) begin       //��ȡ��ѭ����ַ  ���¶�ȡweight 
                data_addr <= base_addr + weight_len;
            end
            else begin
                data_addr <= data_addr + weight_stride;
            end
        end
    end
    assign cmd_addr = data_addr;

    reg cmd_valid_r;
    always @(posedge clk) begin
        if(rst) begin
            cmd_valid_r <= 1'b0;
        end
        else if(cmd_valid & cmd_ready) begin
            cmd_valid_r <= 1'b0;
        end   
        else if(state == WADDR) begin
            cmd_valid_r <= 1'b1;
        end
    end
    assign cmd_valid = cmd_valid_r;



////////////////////////////////////////////�������////////////////////////////////////////////////
    localparam ADDR_WIDTH = $clog2(DATA_DEPTH);
    localparam DEPTH_ADDR = DATA_DEPTH - 1;       //ÿ����ȡȨ�ص���ȵĵ�ַ


/////////////////////////////////////////���ϼ�д�뵱ǰģ��/////////////////////////////////////////
    reg [RAM_CNT_WIDTH-1 : 0] w_ram_cnt;
    always @(posedge clk ) begin
        if(rst)begin
            w_ram_cnt <= 4'd0;
        end
        else if(state == IDLE) begin
            w_ram_cnt <= 4'd0;
        end
        else if((waddr_bias == (calculate_cout_num * CHA_PAR_OUT / BIAS_NUM - 1)) && wen_all) begin                  //д��BIAS
            w_ram_cnt <= 4'd1;
        end 
        else if((waddr == DEPTH_ADDR) && (w_ram_cnt == RAM_CNT) && wen_all) begin                   //��һ��дWEIGHT
            w_ram_cnt <= 4'd1;
        end 
        else if( (waddr == DEPTH_ADDR) && wen_all ) begin       //��0���� -1
            w_ram_cnt <= w_ram_cnt + 4'd1;
        end
    end

    //дʹ��(ȫ��RAM)
    wire wen_all = s_valid & s_ready;
    wire [RAM_CNT-1 : 0] wen;
    
    genvar i;
    generate
        for(i = 1; i <= RAM_CNT; i = i + 1) begin
            assign wen[i-1] = (w_ram_cnt == i) ? wen_all : 1'b0;
        end
    endgenerate

    //д��ַ
    reg [ADDR_WIDTH-1 : 0] waddr;
    always @(posedge clk) begin
        if(rst) begin
            waddr <= {ADDR_WIDTH{1'b0}};
        end
        else if(state == WDATA) begin
            if(wen_all && ( (w_ram_cnt > 0) && (w_ram_cnt <= RAM_CNT) ) ) begin
                if(waddr == DEPTH_ADDR) begin
                    waddr <= {ADDR_WIDTH{1'b0}};
                end
                else begin
                    waddr <= waddr + 1'b1;
                end
            end
        end
    end

    //д����
    wire [DATA_WIDTH-1 : 0] wdata = s_data;

    //д����ź�
    // reg s_ready_r;
    // always @(posedge clk) begin
    //     if(rst) begin
    //         s_ready_r <= 1'b0;
    //     end
    //     else if(state == WADDR) begin
    //         s_ready_r <= 1'b1;
    //     end
    //     else if((state == WDATA) && (next_state == W_WAIT)) begin
    //         s_ready_r <= 1'b0;
    //     end
    // end
    // assign s_ready = s_ready_r;
    assign almost_full_now = (w_ram_cnt == 0) ? 1'b0 : almost_full[RAM_CNT-1];
    assign full_now = (w_ram_cnt == 0) ? 1'b0 : full[RAM_CNT-1];
    assign s_ready = (state == WDATA) && ~full_now;

    localparam BRAM_BITS_TOTAL = 36864 * 2;   //bit �����ֽ� //512���

    parameter integer FIFO_DATA_DEPTH = (DATA_WIDTH <= 72)  ? (BRAM_BITS_TOTAL / 72) :
                                        (DATA_WIDTH <= 144) ? (BRAM_BITS_TOTAL / 144) :
                                                              (BRAM_BITS_TOTAL / DATA_WIDTH);
    localparam ALMOST_FULL_NUM  = FIFO_DATA_DEPTH - CHA_PAR_OUT * MAX_MUL;                     
    //RAM����
    
    wire [DATA_WIDTH-1 : 0] rdata [RAM_CNT-1 : 0];
    generate
        for(i = 0; i < RAM_CNT; i = i + 1) begin

            sync_fifo #(                
                .DATA_WIDTH(DATA_WIDTH),
                .ALMOST_FULL_NUM(ALMOST_FULL_NUM),
                .ALMOST_EMPTY_NUM(CHA_PAR_OUT-1),
                .DATA_DEPTH(FIFO_DATA_DEPTH)         //Vivado�̶�ռ������BRAM
            )
            weight_fifo(
                .clk(clk),
                .rst(rst),
                .wr_en(wen[i]),
                .rd_en(ren[i]),
                .din(wdata),
                .dout(rdata[i]),
                .full(full[i]),
                .almost_full(almost_full[i]),
                .empty(empty[i]),
                .almost_empty(almost_empty[i])
            );

        end
    endgenerate



/////////////////////////////////////////�ӵ�ǰģ��������¼�/////////////////////////////////////////
    wire r_valid;
    wire r_last ;

    //��ѭ��RAM������
    reg [RAM_CNT_WIDTH-1 : 0] r_ram_cnt;
    always @(posedge clk ) begin
        if(rst) begin
            r_ram_cnt <= 4'd1;
        end
        else if(calculate_end) begin
            r_ram_cnt <= 4'd1;
        end
        else if((raddr == DEPTH_ADDR) && (r_ram_cnt == RAM_CNT) && r_valid) begin                   //��һ��дWEIGHT
            r_ram_cnt <= 4'd1;
        end 
        else if(raddr == DEPTH_ADDR) begin       //��0���� -1
            r_ram_cnt <= r_ram_cnt + 4'd1;
        end
    end


    //m_req��m_ready
    reg m_ready;                         
    always @(posedge clk) begin
        if(rst) begin
            m_ready <= 1'b0;
        end
        else if(raddr == DEPTH_ADDR) begin
            m_ready <= 1'b0;
        end 
        else if(m_req & !m_valid) begin
            m_ready <= 1'b1;
        end 
    end


    //��ʹ��(ȫ��RAM)
    wire ren_all = m_ready;
    reg [RAM_CNT-1 : 0] ren;


    integer k;
    always @(posedge clk) begin
        if(rst) begin
            ren <= 0;
        end
        else begin
            if(raddr == DEPTH_ADDR) begin
                for(k = 0; k < RAM_CNT; k = k + 1) begin
                    ren[k] <= 1'b0;
                end
            end
            else begin
                for(k = 0; k < RAM_CNT; k = k + 1) begin
                    if(r_ram_cnt == (k+1) && ~almost_empty[k]) begin
                        ren[k] <= ren_all;
                    end
                end
            end
        end    
    end




    //����ַ
    reg [ADDR_WIDTH-1 : 0] raddr;
    always @(posedge clk ) begin
        if(rst) begin
            raddr <= {ADDR_WIDTH{1'b0}};
        end
        else if(r_valid) begin
            if(raddr == DEPTH_ADDR) begin
                raddr <= {ADDR_WIDTH{1'b0}};
            end
            else begin
                raddr <= raddr + 1'b1;
            end
        end
    end

    assign r_valid = |ren;
    assign r_last  = (raddr == CHA_PAR_OUT-1);     //����Ҫ������жȵ����һ��



    //�������ӳ�  �����´���ȫ����spram���ӳ��йأ�
    reg [READ_DELAY-1 : 0] m_valid_d, m_last_d; 
    always @(posedge clk) begin
        if(rst) begin
            m_valid_d <= 0;
            m_last_d <= 0;
        end
        else begin
            m_valid_d  <= {m_valid_d[READ_DELAY-1 : 0], r_valid};
            m_last_d   <= {m_last_d[READ_DELAY-1 : 0], r_last};
        end
    end

    //���ʱ��
    assign m_valid = m_valid_d[READ_DELAY-1];
    assign m_last  = m_last_d[READ_DELAY-1];
    //���¼��������
    // assign m_data_0 = rdata[0];
    // assign m_data_1 = rdata[1];
    // assign m_data_2 = rdata[2];
    // assign m_data_3 = rdata[3];
    always @(posedge clk) begin
        case(1'b1)
            ren[0]:begin
                m_data_4 <= rdata[0];
            end
            ren[1]:begin
                m_data_4 <= rdata[1];
            end
            default:begin
                m_data_4 <= 0;
            end
        endcase
    end
    // assign m_data_5 = rdata[5];
    // assign m_data_6 = rdata[6];
    // assign m_data_7 = rdata[7];
    // assign m_data_8 = rdata[8];



    //////////////////BIASƫ��///////////////////////////
    localparam ADDR_WIDTH_BIAS = $clog2(BIAS_DEPTH);
    //ƫ��дʹ��
    wire wen_bias = wen_all & (w_ram_cnt == 0);
    //ƫ��д��ַ
    reg [ADDR_WIDTH_BIAS-1 : 0] waddr_bias;
    always @(posedge clk) begin
        if(rst) begin
            waddr_bias <= {ADDR_WIDTH_BIAS{1'b0}};
        end
        else if(state == IDLE) begin
            waddr_bias <= {ADDR_WIDTH_BIAS{1'b0}};
        end
        else if(wen_bias) begin
            waddr_bias <= waddr_bias + 1;
        end
    end
    //ƫ��д����
    wire [BIAS_WIDTH-1:0] wdata_bias;  // ������ generate ���� ȫ�ֿɼ�
    generate
        if(BIAS_NUM == 1) begin
            assign wdata_bias = s_data[BIAS_WIDTH-1 : 0];
        end
        else begin
            assign wdata_bias = {s_data[BIAS_WIDTH +: BIAS_WIDTH/BIAS_NUM], s_data[0 +: BIAS_WIDTH/BIAS_NUM]};
        end
    endgenerate


    //////////////////BIASƫ��///////////////////////////

    //bias_req��bias_ready
    reg bias_ready;                         
    always @(posedge clk) begin
        if(rst) begin
            bias_ready <= 1'b0;
        end
        else if(bias_cnt == BISA_CNT_NUM) begin
            bias_ready <= 1'b0;
        end 
        else if(bias_req & !bias_valid) begin
            bias_ready <= 1'b1;
        end 
    end

    //ƫ�õĸ���������
    reg [$clog2(CHA_PAR_OUT) : 0] bias_cnt;
    always @(posedge clk) begin
        if(rst) begin
            bias_cnt <= 0;
        end
        else if(bias_cnt == BISA_CNT_NUM) begin
            bias_cnt <= 0;
        end
        else if(bias_ready) begin
            bias_cnt <= bias_cnt + 1;
        end
    end


    //ƫ�ö�ʹ��
    wire ren_bias = (bias_cnt < BISA_CNT_NUM) & bias_ready;   //��cntΪ������ж�����Ҫ��biasʱ cnt�Ͳ����� renҲ��������
    //ƫ�ö���ַ
    reg [ADDR_WIDTH_BIAS-1 : 0] raddr_bias;
    always @(posedge clk) begin
        if(rst) begin
            raddr_bias <= {ADDR_WIDTH_BIAS{1'b0}};
        end
        else if(calculate_end) begin
            raddr_bias <= {ADDR_WIDTH_BIAS{1'b0}};
        end
        else if(ren_bias) begin
            if(raddr_bias == (calculate_cout_num * CHA_PAR_OUT / BIAS_NUM - 1)) begin
                raddr_bias <= 0;
            end
            else begin
                raddr_bias <= raddr_bias + 1;
            end
        end
    end



    //���¼����
    wire r_valid_bias = ren_bias;
    wire r_last_bias = ren_bias & (bias_cnt == BISA_CNT_NUM - 1);     //����Ҫ������жȵ����һ��


    //�������ӳ�  �����´���ȫ����spram���ӳ��йأ�
    reg [READ_DELAY-1 : 0] bias_valid_d, bias_last_d; 
    always @(posedge clk) begin
        if(rst) begin
            bias_valid_d <= 0;
            bias_last_d <= 0;
        end
        else begin
            bias_valid_d  <= {bias_valid_d[READ_DELAY-1 : 0], r_valid_bias};
            bias_last_d <= {bias_last_d[READ_DELAY-1 : 0], r_last_bias};
        end
    end

    //RAM����(bias)
    wire [BIAS_WIDTH-1 : 0] rdata_bias;
    spram_D #(.DP(BIAS_DEPTH),    //�洢��Ԫ���
            .DW(BIAS_WIDTH),    //����λ��
            .PIPE(READ_DELAY)  
    ) ram
    (
        .clk   (clk   ),
        .wdata (wdata_bias),
        .wen   (wen_bias),
        .waddr (waddr_bias),
        .ren   (ren_bias),
        .raddr (raddr_bias),
        .rdata (rdata_bias)
    );

    // //���ʱ��
    // assign bias_valid = bias_valid_d[READ_DELAY-1];
    // assign bias_last = bias_last_d[READ_DELAY-1];
    // //ƫ�ö�����
    // assign bias = rdata_bias;


    always @(posedge clk) begin
        bias_valid <= bias_valid_d[READ_DELAY-1];
        bias_last  <= bias_last_d[READ_DELAY-1];
        bias       <= rdata_bias;
    end

endmodule
