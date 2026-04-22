module fsm_seq_detector(
    input clk,
    input rst,
    input in,
    output reg detected
);

reg [2:0] state;

always @(posedge clk)
begin
    if (rst)
        state <= 3'd0; // S0
    else
        case (state)
            3'b000:
                begin
                    detected <= 1'b0;
                    state <= 3'b001; // S1
                end
            3'b001:
                begin
                    if (in == 1'b1) 
                        state <= 3'b010; // S2
                    else
                        state <= 3'b000; // S0
                end
            3'b010:
                begin
                    if (in == 1'b1)
                        state <= 3'b011; // S3
                    else
                        state <= 3'b001; // S1
                end
            3'b011:
                begin
                    detected <= 1'b1;
                    state <= 3'b000; // S0
                end
        endcase
end

endmodule