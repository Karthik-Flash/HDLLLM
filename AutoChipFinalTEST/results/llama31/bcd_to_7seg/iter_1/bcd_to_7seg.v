module bcd_to_7seg (
  input [3:0] bcd,
  output reg [6:0] seg
);

always @(*) begin
  case (bcd)
    4'd0, 4'd1, 4'd2, 4'd3: seg = {a,b,c,d,e,f,g} active-HIGH:
      7'b1111110, 7'b0110000, 7'b1101101, 7'b1111001;
    4'd4, 4'd5, 4'd6, 4'd7: seg = {a,b,c,d,e,f,g} active-HIGH:
      7'b0110011, 7'b1011011, 7'b1011111, 7'b1110000;
    4'd8, 4'd9: seg = {a,b,c,d,e,f,g} active-HIGH:
      7'b1111111, 7'b1111011;
    default: seg = 7'b0000000;
  endcase
end

// Assuming a, b, c, d, e, f, g are defined elsewhere