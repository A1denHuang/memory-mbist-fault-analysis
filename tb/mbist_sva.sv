// Enable with +define+ENABLE_SVA on Questa. Portable equivalents also run in tb.
module mbist_sva(input logic clk, rst_n, done, start, en, we,
                 input logic [7:0] addr, input logic compare_valid, fail_valid);
    default clocking cb @(posedge clk); endclocking
    default disable iff (!rst_n);
    // DONE is sticky until reset, and the interface becomes quiescent.
    assert property (done |=> done && !en && $stable({addr,we}));
    assert property (en |-> !$isunknown(addr));
    assert property ((en && !we) |=> compare_valid);
    assert property (compare_valid |-> $past(en && !we));
    assert property (fail_valid |-> $past(compare_valid));
    assert property (done |-> !en);
endmodule
