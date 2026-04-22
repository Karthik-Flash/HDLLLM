module half_adder  (input a, b, output wire [1:0] out);
    always @(*) begin
        out[0] = a ^ b; // Sum
        out[1] = a & b; // Carry
    end
endmodule