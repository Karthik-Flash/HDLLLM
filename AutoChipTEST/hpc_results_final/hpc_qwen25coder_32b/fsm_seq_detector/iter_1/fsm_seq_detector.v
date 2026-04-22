module fsm_seq_detector (
    input clk,
    input rst,
    input in,
    output detected
);

    localparam S0 = 2'b00;
    localparam S1 = 2'b01;
    localparam S2 = 2'b10;
    localparam S3 = 2'b11;

    reg [1:0] state;
    reg detected_reg;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state <= S0;
            detected_reg <= 0;
        end else begin
            case (state)
                S0: begin
                    if (in == 1) begin
                        state <= S1;
                    end
                    detected_reg <= 0;
                end
                S1: begin
                    if (in == 0) begin
                        state <= S2;
                    end else begin
                        state <= S1;
                    end
                    detected_reg <= 0;
                end
                S2: begin
                    if (in == 1) begin
                        state <= S3;
                    end else begin
                        state <= S2;
                    end
                    detected_reg <= 0;
                end
                S3: begin
                    if (in == 1) begin
                        state <= S1;
                    end else begin
                        state <= S2;
                    end
                    detected_reg <= 1;
                end
                default: begin
                    state <= S0;
                    detected_reg <= 0;
                end
            endcase
        end
    end

    assign detected = detected_reg;

endmodule