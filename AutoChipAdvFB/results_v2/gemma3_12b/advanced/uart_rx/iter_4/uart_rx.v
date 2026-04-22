module uart_rx (
  input clk,
  input rst,
  input rx,
  output reg [7:0] rx_data,
  output reg data_valid
);

  parameter CLKS_PER_BIT = 4;

  reg [7:0] rx_shift;
  reg [2:0] bit_count;
  reg [1:0] state;

  // State definitions
  localparam IDLE = 2'b00;
  localparam START_BIT = 2'b01;
  localparam DATA_RECEIVE = 2'b10;
  localparam STOP_BIT = 2'b11;

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
            state <= START_BIT;
            bit_count <= 0;
          end else begin
            state <= IDLE;
          end
        end
        START_BIT: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= START_BIT;
          end else begin
            state <= DATA_RECEIVE;
            bit_count <= 0;
          end
        end
        DATA_RECEIVE: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= DATA_RECEIVE;
          end else begin
            rx_shift <= {rx_shift[6:0], rx};
            bit_count <= bit_count + 1;
          end
        end
        STOP_BIT: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= STOP_BIT;
          end else begin
            if (!rx) begin
              state <= IDLE;
              data_valid <= 1'b1;
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