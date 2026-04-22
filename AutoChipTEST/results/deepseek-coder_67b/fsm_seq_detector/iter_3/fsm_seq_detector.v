module fsm_seq_detector(input wire clk, rst, in, output reg detected);
    // Define states
    typedef enum logic [1:0] {S0 = 2'b00, S1 = 2'b01, S2 = 2'b10, S3 = 2'b11} state_t;
    state_t state, next_state;
    
    always @(posedge clk or posedge rst) begin
        if (rst) 
            state <= S0; // Reset to idle state on reset signal
        else 
            state <= next_state; // Transition to the next state
    end
    
    always @(*) begin
        detected = 1'b0; // Default value, no sequence detected yet
        
        case (state)
            S3: detected = 1'b1; // If in state S3, a 1011 sequence has been detected
            
            default: ; // Do nothing for other states
        endcase
    end
    
    always @(*) begin
        next_state = state; // Default value, stay at current state
        
        case (state)
            S0: if (in == 1'b1) 
                    next_state = S1; // If in idle state and input is 1, go to state S1
                
            S1: if (in == 1'b0) 
                    next_state = S2; // If in state S1 and input is 0, go to state S2
                
            S2: if (in == 1'b1) 
                    next_state = S3; // If in state S2 and input is 1, go to state S3
                
            default: ; // Do nothing for other states
        endcase
    end
endmodule