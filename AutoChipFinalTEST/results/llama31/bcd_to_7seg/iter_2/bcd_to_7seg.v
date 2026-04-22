module bcd_to_7seg (
  input [3:0] bcd,
  output reg [6:0] seg
);

always @(*) begin
  case (bcd)
    4'b0000, 4'b0001, 4'b0010, 4'b0011: seg = 7'b1111110;
    4'b0100, 4'b0101, 4'b0110, 4'b0111: seg = 7'b0110000;
    4'b1000, 4'b1001, 4'b1010, 4'b1011: seg = 7'b1101101;
    4'b1110, 4'b1111: seg = 7'b1111001;
    4'b00100, 4'b01001, 4'b10010, 4'b10101: seg = 7'b0110011;
    4'b10110, 4'b11011: seg = 7'b1011011;
    4'b11111: seg = 7'b1011111;
    default: seg = 7'b0000000;
  endcase
end

endmodule