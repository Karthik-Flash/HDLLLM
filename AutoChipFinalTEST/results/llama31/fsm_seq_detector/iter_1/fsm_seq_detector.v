module fsm_seq_detector(
  input clk,
  input rst,
  input in,
  output wire detected
);

reg [1:0] state;

always @(posedge clk)
  if (rst) begin
    state <= 2'd0;
  end else begin
    case (state)
      2'd0: if (~in) state <= 2'd0; else state <= 2'd1;
      2'd1: if (~in) state <= 2'd2; else state <= 2'd1;
      2'd2: if (in) state <= 2'd3; else state <= 2'd0;
      2'd3: if (in) state <= 2'd1; else state <= 2'd2;
    endcase
  end

assign detected = (state == 2'd3) & in;

endmodule