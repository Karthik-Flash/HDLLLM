module fsm_seq_detector (
    input wire clk,
    input wire rst,
    input wire in,
    output reg detected
);

    // State encoding: S0 = 2'b00, S1 = 2'b01, S2 = 2'b10, S3 = 2'b11
    reg [1:0] state;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= 2'b00; // Reset to idle state S0
            detected <= 1'b0;
        end else begin
            case (state)
                2'b00: begin // S0 (idle)
                    if (in == 1'b1)
                        state <= 2'b01; // Transition to S1
                    else
                        state <= 2'b00; // Stay in S0
                    detected <= 1'b0;
                end
                2'b01: begin // S1 (got 1)
                    if (in == 1'b0)
                        state <= 2'b10; // Transition to S2
                    else
                        state <= 2'b01; // Stay in S1
                    detected <= 1'b0;
                end
                2'b10: begin // S2 (got 10)
                    if (in == 1'b1)
                        state <= 2'b11; // Transition to S3
                    else
                        state <= 2'b00; // Reset to S0
                    detected <= 1'b0;
                end
                2'b11: begin // S3 (got 101)
                    if (in == 1'b1)
                        state <= 2'b11; // Stay in S3 for overlapping sequences
                    else
                        state <= 2'b00; // Reset to S0
                    detected <= 1'b1; // Sequence detected
                end
            endcase
        end
    end

endmodule