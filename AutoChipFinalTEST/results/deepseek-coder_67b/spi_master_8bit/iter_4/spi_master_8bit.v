module spi_master_8bit(input wire clk, rst, start, input [7:0] mosi_data, input miso, output reg sclk, cs_n, mosi, done, output reg [7:0] miso_capture);
    parameter CLK_DIV = 4;
    
    typedef enum {IDLE=2'd0, ACTIVE=2'd1, DONE_ST=2'd2} state_t;
    state_t state, next_state;
    
    reg [7:0] shift_out, shift_in; 
    reg [3:0] clk_cnt, bit_cnt;
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= IDLE;
            cs_n <= 1'b1;
            sclk <= 1'b0;
            mosi <= 1'b0;
            done <= 1'b0;
            miso_capture <= 8'd0;
        end 
        else begin
            state <= next_state;
            
            case (state)
                IDLE: begin
                    cs_n <= 1'b1;
                    sclk <= 1'b0;
                    done <= 1'b0;
                end
                
                ACTIVE: begin
                    if(clk_cnt < CLK_DIV) begin 
                        sclk <= 1'b0;
                        mosi <= shift_out[7];
                    end 
                    else if (clk_cnt == CLK_DIV - 1) begin
                        sclk <= 1'b1;
                    end 
                    else begin
                        sclk <= 1'b1;
                        
                        if(clk_cnt == 2*CLK_DIV - 2) begin
                            shift_in <= {shift_in[6:0], miso};
                        end 
                        else if (clk_cnt == 2*CLK_DIV - 1) begin
                            sclk <= 1'b0;
                            shift_out <= {shift<beginofsentence>