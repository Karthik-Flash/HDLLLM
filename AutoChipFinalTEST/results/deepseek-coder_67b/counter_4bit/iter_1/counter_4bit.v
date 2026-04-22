module counter_4bit(input clk, rst, output reg [3:0] count);
  
  always @(posedge clk) begin
    if (rst) 
      count <= 4'b0;
    else 
      count <= count + 1'b1;
      
    // Wraps naturally 15->0
    if (count == 4'd15)
      count <= 4'b0;
  end
endmodule