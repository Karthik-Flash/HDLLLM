module uart_rx (
  input clk,
  input rst,
  input rx,
  output reg [7:0] rx_data,
  output reg data_valid
);

  parameter CLKS_PER_BIT = 4;

  reg [7:0] rx_shift;
  reg [3:0] bit_count; // Increased width to 4 bits
  reg [1:0] state;

  // State definitions
  localparam IDLE = 2'b00;
  localparam START = 2'b01;
  localparam RX_DATA = 2'b10;
  localparam STOP = 2'b11;

  always @(posedge clk) begin
    if (rst) begin
      state <= IDLE;
      rx_data <= 8'h00;
      data_valid <= 1'b0;
      bit_count <= 0;
    end else begin
      case (state)
        IDLE: begin
          if (!rx) begin
            state <= START;
            bit_count <= 0;
          end else begin
            state <= IDLE;
          end
        end
        START: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= START;
          end else begin
            state <= RX_DATA;
            bit_count <= 0;
          end
        end
        RX_DATA: begin
          if (bit_count < 8) begin
            rx_shift <= {rx_shift[6:0], rx};
            bit_count <= bit_count + 1;
            state <= RX_DATA;
          end else begin
            state <= STOP;
            bit_count <= 0;
          end
        end
        STOP: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= STOP;
          end else begin
            if (!rx) begin
              data_valid <= 1'b1;
              state <= IDLE;
            end else begin
              state <= IDLE;
            end
          end
        end
        default: begin
          state <= IDLE;
          data_valid <= 1'b0;
        end
      endcase
    end
  end

endmodule