`timescale 1ns/1ps
module tb_fault_model;
    sram_fault_model m(.clk(1'b0),.en(1'b0),.we(1'b0),.addr(8'b0),.wdata(1'b0),.rdata());
    bit unused;
    integer checks=0,i;
    task check(input bit condition, input string label_text);
        begin
            checks=checks+1;
            if (!condition) $fatal(1,"Fault-model unit test failed: %s",label_text);
        end
    endtask
    task configure(input integer kind, input integer value, input integer trigger);
        begin
            m.initialize(); m.fault_count=1; m.types[0]=kind;
            m.victims[0]=17; m.aggressors[0]=34;
            m.values[0]=value; m.triggers[0]=trigger; m.thresholds[0]=10;
        end
    endtask
    initial begin
        #1;
        configure(1,0,0); unused=m.do_write(17,1,1); check(m.do_read(17,2)==0,"SAF0");
        configure(2,0,0); check(m.do_read(17,2)==1,"SAF1");
        configure(3,0,0); unused=m.do_write(17,1,1); check(m.do_read(17,2)==0,"TF up");
        configure(4,0,0); unused=m.do_write(17,1,1); unused=m.do_write(17,0,2);
        check(m.do_read(17,3)==1,"TF down");
        configure(5,0,0); unused=m.do_write(34,1,1); check(m.do_read(17,2)==1,"CFin rising");
        unused=m.do_write(34,0,3); check(m.do_read(17,4)==0,"CFin falling");
        configure(6,1,1); unused=m.do_write(34,1,1); check(m.do_read(17,2)==1,"CFid rising");
        configure(6,1,0); unused=m.do_write(34,1,1); check(m.do_read(17,2)==0,"CFid inactive");
        unused=m.do_write(34,0,3); check(m.do_read(17,4)==1,"CFid falling");
        configure(7,1,0); check(m.do_read(17,1)==1,"CFst active state");
        unused=m.do_write(34,1,2); unused=m.do_write(17,0,3);
        check(m.do_read(17,4)==0,"CFst inactive state");
        configure(8,0,0); unused=m.do_write(17,1,1); check(m.do_read(34,2)==1,"AF alias");
        unused=m.do_write(34,0,3); check(m.do_read(17,4)==0,"AF reverse observation");
        configure(9,1,0);
        for(i=16;i<32;i=i+1) check(m.do_read(i,1)==1,"Row fault span");
        check(m.do_read(32,1)==0,"Row isolation");
        configure(10,1,0);
        for(i=1;i<256;i=i+16) check(m.do_read(i,1)==1,"Column fault span");
        check(m.do_read(2,1)==0,"Column isolation");
        configure(11,0,0); unused=m.do_write(17,1,1);
        check(m.do_read(17,10)==1,"DRF before threshold");
        check(m.do_read(17,11)==0,"DRF at threshold");
        check(m.do_read(17,12)==0,"DRF flips once");
        unused=m.do_write(17,1,13); check(m.do_read(17,14)==1,"DRF write rearms");
        $display("PASS fault-model unit checks=%0d",checks); $finish;
    end
endmodule
