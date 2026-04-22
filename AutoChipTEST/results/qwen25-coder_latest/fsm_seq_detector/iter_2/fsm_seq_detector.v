module fsm_seq_detector (
    input clk,
    input rst,
    input in,
    output reg detected
);

    // State declarations
    localparam S0 = 2'b00;
    localparam S1 = 2'b01;
    localparam S2 = 2'b10;
    localparam S3 = 2'b11;

    // Current state and next state signals
    reg [1:0] current_state, next_state;

    // Output signal declaration
    wire detected_wire;

    // State transition logic
    always @(posedge clk or posedge rst) begin
        if (rst)
            current_state <= S0;
        else
            current_state <= next_state;
    end

    // Next state and output assignment
    assign next_state = case (current_state)
        S0: in ? S1 : S0,
        S1: in ? S2 : S0,
        S2: in ? S3 : S0,
        S3: in ? S3 : S0,
        default: S0
    endcase;

    assign detected_wire = (current_state == S3);

    // Output assignment
    always @(posedge clk or posedge rst) begin
        if (rst)
            detected <= 1'b0;
        else
            detected <= detected_wire;
    end

endmodule