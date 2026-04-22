module fsm_seq_detector (
    input clk,
    input rst,
    input in,
    output wire detected
);

reg [1:0] state;

// State transition logic
always @(posedge clk or posedge rst) begin
    if (rst)
        state <= 2'd0; // Reset to S0
    else
        case (state)
            2'd0: state <= in ? 2'd1 : 2'd0;
            2'd1: state <= in ? 2'd1 : 2'd2;
            2'd2: state <= in ? 2'd3 : 2'd0;
            2'd3: state <= in ? 2'd1 : 2'd2;
        endcase
end

// Combinational output logic
assign detected = (state == 2'd3) & in;

endmodule