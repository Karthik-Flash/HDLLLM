module fsm_seq_detector(input clk, rst, in, output wire detected);
    reg [1:0] state;
    
    always @(posedge clk or posedge rst) begin
        if (rst) 
            state <= 2'd0; // Reset to S0 on reset signal
        else 
            case (state)
                2'd0: state <= in ? 2'd1 : 2'd0; // If input is 1, go to S1, stay at S0 otherwise
                2'd1: state <= !in ? 2'd2 : 2'd1; // If input is 0, go to S2, stay at S1 otherwise
                2'd2: state <= in ? 2'd3 : 2'd0; // If input is 1, go to S3, reset to S0 otherwise
                default: state <= !in ? 2'd3 : 2'd2; // For state S3, if input is 0, go back to S2, stay at S3 otherwise
            endcase
    end
    
    assign detected = (state == 2'd3) & in; // Output 'detected' fires when the state is S3 and input is 1
endmodule