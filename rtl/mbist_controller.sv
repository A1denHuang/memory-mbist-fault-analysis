`timescale 1ns/1ps
// March C-: w0; up(r0,w1); up(r1,w0); down(r0,w1);
// down(r1,w0); up(r0). Each read is followed by a compare cycle.
module mbist_controller #(
    parameter integer ADDR_WIDTH = 8,
    parameter integer RETENTION_CYCLES = 0
) (
    input wire clk, rst_n, start, stop_on_fail,
    output wire en, we,
    output wire [ADDR_WIDTH-1:0] addr,
    output wire wdata,
    input wire rdata,
    output reg done, pass,
    output reg fail_valid,
    output reg [ADDR_WIDTH-1:0] fail_addr,
    output reg [2:0] fail_element,
    output reg fail_op, expected, actual,
    output wire compare_valid,
    output wire [2:0] element,
    output reg [31:0] operation_count
);
    localparam [2:0] IDLE=0, ISSUE=1, CHECK=2, HOLD=3, FINISHED=4;
    localparam [ADDR_WIDTH-1:0] LAST = {ADDR_WIDTH{1'b1}};
    reg [2:0] state, march_element;
    reg [ADDR_WIDTH-1:0] address, read_addr;
    reg write_phase, stop_latched, read_expected;
    reg [2:0] read_element;
    reg [31:0] hold_count;
    wire descending = march_element == 3 || march_element == 4;
    wire last_addr = descending ? address == 0 : address == LAST;
    wire exp_bit = march_element == 2 || march_element == 4;
    assign en = state == ISSUE;
    assign we = march_element == 0 || write_phase;
    assign addr = address;
    assign wdata = (march_element == 1 || march_element == 3);
    assign compare_valid = state == CHECK;
    assign element = march_element;

    task advance_address;
        begin
            write_phase <= 0;
            if (!last_addr) address <= descending ? address - 1'b1 : address + 1'b1;
            else if (march_element == 5) begin
                done <= 1;
                state <= FINISHED;
            end else begin
                march_element <= march_element + 1'b1;
                address <= (march_element == 2 || march_element == 3) ? LAST : 0;
                if (march_element == 0 && RETENTION_CYCLES > 0) begin
                    hold_count <= RETENTION_CYCLES;
                    state <= HOLD;
                end
            end
        end
    endtask

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE; march_element <= 0; address <= 0;
            write_phase <= 0; stop_latched <= 0; hold_count <= 0;
            read_addr <= 0; read_expected <= 0; read_element <= 0;
            done <= 0; pass <= 1; fail_valid <= 0;
            fail_addr <= 0; fail_element <= 0; fail_op <= 0;
            expected <= 0; actual <= 0; operation_count <= 0;
        end else begin
            fail_valid <= 0;
            case (state)
                IDLE: if (start) begin
                    state <= ISSUE; stop_latched <= stop_on_fail;
                end
                ISSUE: begin
                    operation_count <= operation_count + 1;
                    if (we) advance_address();
                    else begin
                        read_addr <= address; read_element <= march_element;
                        read_expected <= exp_bit; state <= CHECK;
                    end
                end
                CHECK: begin
                    if (rdata != read_expected) begin
                        pass <= 0; fail_valid <= 1;
                        fail_addr <= read_addr; fail_element <= read_element;
                        fail_op <= read_expected;
                        expected <= read_expected; actual <= rdata;
                    end
                    if (rdata != read_expected && stop_latched) begin
                        done <= 1; state <= FINISHED;
                    end else begin
                        state <= ISSUE;
                        if (march_element == 5) advance_address();
                        else write_phase <= 1;
                    end
                end
                HOLD: begin
                    if (hold_count <= 1) state <= ISSUE;
                    else hold_count <= hold_count - 1;
                end
                FINISHED: state <= FINISHED; // reset required before another run
                default: state <= IDLE;
            endcase
        end
    end
endmodule
