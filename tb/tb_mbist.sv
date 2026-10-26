`timescale 1ns/1ps
module tb_mbist;
    parameter integer RETENTION_CYCLES=0;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0,start=0,stop_on_fail=0;
    wire en,we,wdata,rdata,done,pass,fail_valid,fail_op,expected,actual,compare_valid;
    wire [7:0] addr,fail_addr;
    wire [2:0] element,fail_element;
    wire [31:0] operation_count;
    mbist_controller #(.RETENTION_CYCLES(RETENTION_CYCLES)) dut(.*);
    sram_fault_model memory(.clk(clk),.en(en),.we(we),.addr(addr),.wdata(wdata),.rdata(rdata));
    // Same fault model, independent memory contents, software March sequence.
    sram_fault_model reference_memory(.clk(1'b0),.en(1'b0),.we(1'b0),
        .addr(8'b0),.wdata(1'b0),.rdata());
    integer seed=0,mode=0,cycle=0,fd,tf,ops=0,fails=0,finished_cycles=0;
    integer ref_element,ref_addr,offset,local_index;
    integer pending_addr,pending_element;
    integer coverage_kind=0, address_order=2;
    bit ref_we,ref_data,pending=0,pending_expected,pending_actual,check_fail=0,unused;
    bit previous_read=0,done_seen=0;
    reg [8:0] frozen_bus;
    string cfg,logfile,summary,tracefile,wavefile;
    initial begin
        if (!$value$plusargs("CFG=%s",cfg)) $fatal(1,"Missing +CFG=file");
        if (!$value$plusargs("LOG=%s",logfile)) logfile="fails.csv";
        if (!$value$plusargs("SUMMARY=%s",summary)) summary="summary.txt";
        unused=$value$plusargs("SEED=%d",seed);
        unused=$value$plusargs("STOP=%d",mode);
        stop_on_fail=mode!=0;
        #1;
        memory.initialize(); reference_memory.initialize();
        memory.load_config(cfg); reference_memory.load_config(cfg);
        if (memory.fault_count==1) begin
            coverage_kind=memory.types[0];
            if (coverage_kind>=5 && coverage_kind<=7)
                address_order=memory.aggressors[0]<memory.victims[0] ? 0 : 1;
        end
        fd=$fopen(logfile,"w");
        if (!fd) $fatal(1,"Cannot create fail log");
        $fdisplay(fd,"seed,addr,row,col,element,op,expected,actual");
        tf=0;
        if ($value$plusargs("TRACE=%s",tracefile)) begin
            tf=$fopen(tracefile,"w");
            $fdisplay(tf,"cycle,element,addr,we,data");
        end
        if ($value$plusargs("VCD=%s",wavefile)) begin
            $dumpfile(wavefile); $dumpvars(0,tb_mbist);
        end
        repeat (3) @(negedge clk);
        rst_n=1; start=1;
        @(negedge clk); start=0;
    end

    // Software sequence derived from the operation index, independent of DUT state.
    always @(posedge clk) begin
        cycle=cycle+1; check_fail=0;
        if (rst_n) begin
            if (compare_valid !== previous_read) $fatal(1,"Read latency assertion");
            previous_read=en && !we;
            if (compare_valid) begin
                if (!pending) $fatal(1,"Comparison without a reference read");
                check_fail=pending_actual!=pending_expected;
                pending=0;
            end
            if (en) begin
                if (ops>=2560) $fatal(1,"Excess operations");
                if (ops<256) begin ref_element=0; ref_addr=ops; ref_we=1; ref_data=0; end
                else if (ops<2304) begin
                    offset=ops-256; ref_element=1+offset/512;
                    local_index=(offset%512)/2;
                    ref_addr=ref_element>=3 ? 255-local_index : local_index;
                    ref_we=offset%2;
                    ref_data=ref_element==1 || ref_element==3;
                    if (!ref_we) ref_data=~ref_data;
                end else begin ref_element=5; ref_addr=ops-2304; ref_we=0; ref_data=0; end
                if (addr!==ref_addr[7:0] || we!==ref_we || element!==ref_element[2:0] ||
                    (we && wdata!==ref_data))
                    $fatal(1,"Sequence mismatch at operation %0d",ops);
                if (tf) $fdisplay(tf,"%0d,M%0d,%0d,%0d,%0d",cycle,ref_element,ref_addr,ref_we,ref_data);
                if (ref_we) unused=reference_memory.do_write(ref_addr,ref_data,cycle);
                else begin
                    pending=1; pending_addr=ref_addr; pending_element=ref_element;
                    pending_expected=ref_data;
                    pending_actual=reference_memory.do_read(ref_addr,cycle);
                end
                ops=ops+1;
            end
        end
    end
    always @(negedge clk) if (rst_n) begin
        if (fail_valid !== check_fail) $fatal(1,"Failure-valid mismatch at cycle %0d",cycle);
        if (fail_valid) begin
            if (fail_addr!==pending_addr[7:0] || fail_element!==pending_element[2:0] ||
                expected!==pending_expected || actual!==pending_actual || fail_op!==pending_expected)
                $fatal(1,"Failure tuple mismatch");
            fails=fails+1;
            $fdisplay(fd,"%0d,0x%02h,%0d,%0d,M%0d,r%0d,%0d,%0d",seed,fail_addr,
                fail_addr/16,fail_addr%16,fail_element,fail_op,expected,actual);
        end
        if (done_seen && {addr,we}!==frozen_bus) $fatal(1,"DONE interface changed");
        if (done) begin
            if (en || pending) $fatal(1,"DONE with outstanding operation");
            if (!done_seen) begin
                done_seen=1; frozen_bus={addr,we};
                if (pass !== (fails==0)) $fatal(1,"PASS mismatch");
                if (operation_count!==ops) $fatal(1,"Operation count mismatch");
                if (mode==0 && ops!=2560) $fatal(1,"Incomplete diagnostic run");
                if (mode!=0 && fails>1) $fatal(1,"Stop mode reported multiple failures");
            end
            finished_cycles=finished_cycles+1;
            if (finished_cycles==4) begin
                $fclose(fd); if (tf) $fclose(tf);
                fd=$fopen(summary,"w");
                $fdisplay(fd,"operations=%0d failures=%0d pass=%0d cycles=%0d",ops,fails,pass,cycle);
                $fclose(fd);
                $display("PASS seed=%0d stop=%0d operations=%0d failures=%0d",seed,mode,ops,fails);
                $finish;
            end
        end
        if (cycle>RETENTION_CYCLES+10000) $fatal(1,"Watchdog expired");
    end
`ifdef ENABLE_SVA
    mbist_sva assertions(.*);
    mbist_coverage coverage_inst(.clk(clk),.rst_n(rst_n),.en(en),.stop_on_fail(stop_on_fail),
        .fail_valid(fail_valid),.addr(addr),.fail_addr(fail_addr),.element(element),
        .fail_element(fail_element),.fault_kind(coverage_kind),.address_order(address_order));
`endif
endmodule
