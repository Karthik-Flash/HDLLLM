module uart_tx  #(parameter BAUD_DIV = 104) (input clk, rst, start, input [7:0] data_in, output reg tx_out, busy, done);
  
  // State definitions
  typedef enum {IDLE=3'd0, START=3'd1, DATA=3'd2, STOP=3'd3, DONE=3'd4} state_t;
  
  // Internal registers
  reg [7:0] shift_reg;
  reg [7:0] baud_cnt;
  reg [3:0] bit_cnt;
  
  // State variable
  state_t state, next_state;
  
  // Combinational logic for next state and outputs
  always @(*) begin
    case (state)
      IDLE : begin
        tx_out <= 1'b1;
        busy   <= 1'b0;
        done   <= 1'b0;
        if (start == 1'b1) begin
          next_state <= START;
        end else begin
          next_state <= IDLE;
        end
      end
      
      START : begin
        tx_out <= 1'b0;
        busy   <= 1'b1;
        done   <= 1'b0;
        if (baud_cnt == BAUD_DIV - 1) begin
          next_state <= DATA;
        end else begin
          next_state <= START;
        end
      end
      
      DATA : begin
        tx_out <= shift_reg[0];
        busy   <= 1'b1;
        done   <= 1'b0;
        if (baud_cnt == BAUD_DIV - 1) begin
          next_state <= bit_cnt == 4'd7 ? STOP : DATA;
        end else begin
          next_state <= DATA;
        end
      end
      
      STOP : begin
        tx_out <= 1'b1;
        busy   <= 1'b1;
        done   <= 1'b0;
        if (baud_cnt == BAUD_DIV - 1) begin
          next_state <= DONE;
        end else begin
          next_state <= STOP;
        end
      end
      
      DONE : begin
        tx_out <= 1'b1;
        busy   <= 1'b0;
        done   <= 1'b1;
        next_state <= IDLE;
      end
    endcase
  end
  
  // Sequential logic for state transitions and register updates
  always @(posedge clk or posedge rst) begin
    if (rst == 1'b1) begin
      state    <= IDLE;
      shift_reg <= 8'd0;
      baud_cnt  <= 8'd0;
      bit_cnt   <= 4'd0;
    end else begin
      state <= next_state;
      if (start == 1'b1) begin
        shift_reg <= data_in;
        baud_cnt <= 8'd0;
        bit_cnt  <= 4'd0;
      end else if ((baud_cnt == BAUD_DIV - 1) && (state != DONE)) begin
        baud_cnt <= 8'd0;
        case (state)
          START : state <= DATA;
          DATA  : begin
            shift_reg <= {1'b0, shift_reg[7:1]};
            bit_cnt   <= bit_cnt + 4'd1;
          end
          STOP  : state <= DONE;
        endcase
      end else if (baud_cnt < BAUD_DIV - 1) begin
        baud_cnt <= baud_cnt + 8'd1;
      end
    end
  end
endmodule