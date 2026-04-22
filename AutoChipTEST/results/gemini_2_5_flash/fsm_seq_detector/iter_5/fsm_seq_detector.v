module fsm_seq_detector (
    input clk,
    input rst,
    input in,
    output reg detected // Declared as output reg, as it's assigned inside an always block
);

    // State declarations using localparam
    localparam S0 = 2'b00; // Initial state: waiting for '1'
    localparam S1 = 2'b01; // Received '1': waiting for '0'
    localparam S2 = 2'b10; // Received '10': waiting for '1'
    localparam S3 = 2'b11; // Received '101': waiting for '1'

    // State registers
    reg [1:0] current_state;
    reg [1:0] next_state; // Used for combinational next state logic

    // Synchronous reset and state update logic
    // The reset is synchronous, so it's only sensitive to the positive edge of clk.
    always @(posedge clk) begin
        if (rst) begin
            current_state <= S0;
        end else begin
            current_state <= next_state;
        end
    end

    // Next state and Mealy output combinational logic
    // 'detected' is a Mealy output, meaning it depends on current state AND current input.
    // Since 'detected' is declared as 'reg' and assigned in an always block,
    // it must be assigned using blocking assignments in this combinational block.
    always @(*) begin
        // Default assignments to avoid latches
        next_state = current_state;
        detected = 1'b0; // Default to 0, only set to 1 when sequence is detected

        case (current_state)
            S0: begin // Waiting for the first '1'
                if (in == 1'b1) begin
                    next_state = S1;
                end else begin // in == 0
                    next_state = S0;
                end
            end
            S1: begin // Received '1', waiting for '0'
                if (in == 1'b0) begin
                    next_state = S2;
                end else begin // in == 1 (overlapping '1')
                    next_state = S1;
                end
            end
            S2: begin // Received '10', waiting for '1'
                if (in == 1'b1) begin
                    next_state = S3;
                end else begin // in == 0 (sequence broken '100')
                    next_state = S0; // Restart from S0
                end
            end
            S3: begin // Received '101', waiting for the final '1'
                if (in == 1'b1) begin
                    // Sequence "1011" detected!
                    // Assert detected=1 on the clock cycle the LAST bit of 1011 arrives.
                    detected = 1'b1;
                    // Overlapping sequence: The last '1' can be the start of a new '1'
                    next_state = S1; // Transition to S1 (received '1')
                end else begin // in == 0 (sequence broken '1010')
                    // Overlapping sequence: "1010" contains "10"
                    next_state = S2; // Transition to S2 (received '10')
                end
            end
            default: begin
                // Should not happen in a properly designed FSM
                next_state = S0;
                detected = 1'b0;
            end
        endcase
    end

endmodule