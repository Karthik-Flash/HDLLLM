module spi_master_8bit   (input wire clk, rst, start, input  [7:0] mosi_data, input miso, output reg sclk, cs_n, mosi, done, output reg  [7:0] miso_capture);
    parameter CLK_DIV  = 4; // Corrected semicolon missing here
    
    typedef enum {IDLE=2'd0, ACTIVE=2'd1, DONE=2'd2} state_t; 
    state_t state, next_state;
    
    reg [7:0] shift_out, shift_in; // Corrected semicolon missing here
    reg [3:0] clk_cnt, bit_cnt; // Corrected semicolon missing here
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= IDLE; 
            cs_n <= 1'b1;
            sclk <= 1'b0;
            mosi <= 1'b0;
            done <= 1'b0;
            miso_capture <= 8'd0; // Corrected semicolon missing here
        end 
        else begin
            state <= next_state;
            
            case (state)
                IDLE: begin
                    cs_n <= 1'b1;
                    sclk <= 1'b0;
                    done <= 1'b0; // Corrected semicolon missing here
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
                            shift_in <= {shift_in[6:0], miso}; // Corrected semicolon missing here
                        end 
                        else if (clk_cnt == 2*CLK_DIV - 1) begin
                            sclk <= 1'b0;
                            shift_out <= {shift_out[6:0], 1'b0}; // Corrected semicolon missing here
                            clk_cnt <= 4'd0; // Corrected semicolon missing here
                            bit_cnt <= bit_cnt + 1'b1; // Corrected semicolon missing here
                        end 
                    end 
                end
                
                DONE: begin
                    done <= 1'b1; // Corrected semicolon missing here
                    miso_capture <= shift_in; // Corrected semicolon missing here
                    next_state <= IDLE; // Corrected semicolon missing here
                end
            endcase
            
            if(start) begin
                cs_n <= 1'b0;
                shift_out <= mosi_data; // Corrected semicolon missing here
                bit_cnt <= 4'd0; // Corrected semicolon missing here
                clk_cnt <= 4'd0; // Corrected semicolon missing here
                next_state <= ACTIVE; // Corrected semicolon missing here
            end 
        end
    end
endmodule