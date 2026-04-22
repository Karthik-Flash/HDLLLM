module fsm_seq_detector (
    input wire clk,
    input wire rst,
    input wire in,
    output reg detected
);

    // State declarations
    localparam S0 = 2'b00;
    localparam S1 = 2'b01;
    localparam S2 = 2'b10;
    localparam S3 = 2'b11;

    // State register
    reg [1:0] current_state;

    // Combinational logic for next state and output
    always @(*) begin
        detected = 0; // Default value for detected
        case (current_state)
            S0: begin
                if (in == 1)
                    detected = 0;
            end
            S1: begin
                if (in == 0)
                    detected = 0;
            end
            S2: begin
                if (in == 1)
                    detected = 0;
            end
            S3: begin
                if (in == 1)
                    detected = 1;
                else
                    detected = 0;
            end
        endcase
    end

    // Sequential logic for state transition
    always @(posedge clk or posedge rst) begin
        if (rst)
            current_state <= S0;
        else
            case (current_state)
                S0: begin
                    if (in == 1)
                        current_state <= S1;
                    else
                        current_state <= S0;
                end
                S1: begin
                    if (in == 0)
                        current_state <= S2;
                    else
                        current_state <= S1;
                end
                S2: begin
                    if (in == 1)
                        current_state <= S3;
                    else
                        current_state <= S2;
                end
                S3: begin
                    if (in == 1)
                        current_state <= S1;
                    else
                        current_state <= S2;
                end
            endcase
    end

endmodule