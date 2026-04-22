module fsm_seq_detector (
  input clk,
  input rst,
  input in,
  output wire detected
);

  reg [1:0] state;

  always @(posedge clk) begin
    if (rst) begin
      state <= 2'd0;
    end else begin
      case (state)
        2'd0: begin
          if (in)
            state <= 2'd1;
          else
            state <= 2'd0;
        end
        2'd1: begin
          if (!in)
            state <= 2'd2;
          else
            state <= 2'd1;
        end
        2'd2: begin
          if (in)
            state <= 2'd3;
          else
            state <= 2'd0;
        end
        2'd3: begin
          if (in)
            state <= 2'd1;
          else
            state <= 2'd2;
        end
        default: state <= 2'd0;
      endcase
    end
  end

  assign detected = (state == 2'd3) & in;

endmodule