module priority_enc_8 (
  input [7:0] in,
  output reg [2:0] out,
  output reg valid
);

  always @(*) begin
    if (in[7]) begin
      out = 3'd7;
      valid = 1;
    end else if (in[6]) begin
      out = 3'd6;
      valid = 1;
    end else if (in[5]) begin
      out = 3'd5;
      valid = 1;
    end else if (in[4]) begin
      out = 3'd4;
      valid = 1;
    end else if (in[3]) begin
      out = 3'd3;
      valid = 1;
    end else if (in[2]) begin
      out = 3'd2;
      valid = 1;
    end else if (in[1]) begin
      out = 3'd1;
      valid = 1;
    end else if (in[0]) begin
      out = 3'd0;
      valid = 1;
    end else begin
      out = 3'd0;
      valid = 0;
    end
  end

endmodule