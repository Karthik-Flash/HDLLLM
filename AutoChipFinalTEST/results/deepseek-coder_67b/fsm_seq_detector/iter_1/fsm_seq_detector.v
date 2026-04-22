module fsm_seq_detector(input clk, rst, in, output wire detected);
    reg [1:0] state;
    wire [1:0] next_state;
    
    // State register with synchronous reset to S0
    always @(posedge clk or posedge rst) begin
        if (rst) 
            state <= 2'd0;
        else 
            state <= next_state;
    end
    
    // Next state logic
    always @(*) begin
        case (state)
            2'd0: next_state = in ? 2'd1 : 2'd0;
            2'd1: next_state = !in ? 2'd2 : 2'd1;
            2'd2: next_state = in ? 2'd3 : 2'd0;
            default: next_state = !in ? 2'd1 : 2'd2; // S3 state
        endcase
    end
    
    // Combinational output
    assign detected = (state == 2'd3) & in;
endmodule