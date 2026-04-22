module bcd_to_7seg (
  input  [3:0] bcd,
  output reg [6:0] seg
);

  always @(*) begin
    case (bcd)
      4'h0: seg = 7'b1111110; // Digit 0
      4'h1: seg = 7'b0110000; // Digit 1
      4'h2: seg = 7'b1101101; // Digit 2
      4'h3: seg = 7'b1111001; // Digit 3
      4'h4: seg = 7'b0110011; // Digit 4
      4'h5: seg = 7'b1011011; // Digit 5
      4'h6: seg = 7'b1011111; // Digit 6
      4'h7: seg = 7'b1110000; // Digit 7
      4'h8: seg = 7'b1111111; // Digit 8
      4'h9: seg = 7'b1111011; // Digit 9
      default: seg = 7'b0000000; // All other BCD values (A-F)
    endcase
  end

endmodule