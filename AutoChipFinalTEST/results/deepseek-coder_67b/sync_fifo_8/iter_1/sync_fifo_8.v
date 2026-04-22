module sync_fifo_8(input clk, rst, wr_en, rd_en, input [7:0] din, output reg [7:0] dout, output wire full, empty);
  // Internal Registers
  reg [7:0] mem[0:7];
  reg [3:0] wr_ptr, rd_ptr;
  
  // Output Assignments
  assign empty = (wr_ptr == rd_ptr);
  assign full  = ((wr_ptr[2:0] == rd_ptr[2:0]) && (wr_ptr[3] != rd_ptr[3]));
  
  // Synchronous Process
  always @(posedge clk or posedge rst) begin
    if(rst) begin
      wr_ptr <= 4'b0;
      rd_ptr <= 4'b0;
      dout   <= 8'b0;
    end else begin
      if (wr_en && !full) begin
        mem[wr_ptr[2:0]] <= din;
        wr_ptr            <= wr_ptr + 1;
      end
      
      if (rd_en && !empty) begin
        dout   <= mem[rd_ptr[2:0]];
        rd_ptr <= rd_ptr + 1;
      end
    end
  end
endmodule