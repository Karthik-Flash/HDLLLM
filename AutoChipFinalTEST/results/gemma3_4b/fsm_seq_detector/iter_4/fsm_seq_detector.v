module fsm_seq_detector (
  input clk,
  input rst,
  input in,
  output wire detected
);

  reg [1:0] state;
  wire detected;

  localparam S0 = 2'd0;
  localparam S1 = 2'd1;
  localparam S2 = 2'd2;
  localparam S3 = 2'd3;

  always @(posedge clk or posedge rst) begin
    if (rst) begin
      state <= S0;
    end else begin
      case (state)
        S0: begin
          if (in == 1) begin
            state <= S1;
          end else begin
            state <= S0;
          end
        end
        S1: begin
          if (in == 0) begin
            state <= S2;
          end else begin
            state <= S1;
          end
        end
        S2: begin
          if (in == 1) begin
            state <= S3;
          end else begin
            state <= S0;
          end
        end
        S3: begin
          if (in == 1) begin
            state <= S1;
          end else begin
            state <= S2;
          end
        end
      endcase
    end
  end

  detected = (state == S3) ? in : 0;

endmodule