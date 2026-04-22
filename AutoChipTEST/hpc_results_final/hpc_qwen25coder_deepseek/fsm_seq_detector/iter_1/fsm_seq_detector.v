module fsm_seq_detector (
    input clk,
    input rst,
    input in,
    output reg detected
);

    reg [1:0] state, next_state;
    localparam S0 = 2'b00, S1 = 2'b01, S2 = 2'b10, S3 = 2'b11;

    always @(posedge clk or posedge rst) begin
        if (rst)
            state <= S0;
        else
            state <= next_state;
    end

    always @(*) begin
        next_state = state;
        detected = 0;
        case (state)
            S0: if (in == 1) next_state = S1;
            S1: if (in == 0) next_state = S2;
            S2: if (in == 1) next_state = S3;
            S3: if (in == 1) begin
                    next_state = S1;
                    detected = 1;
                end else if (in == 0) next_state = S2;
        endcase
    end

endmodule