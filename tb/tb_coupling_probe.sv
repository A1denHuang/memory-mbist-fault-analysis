`timescale 1ns/1ps
// Diagnostic microsequence; observes the synchronous port, never fault fields.
module tb_coupling_probe;
    reg clk=0;
    always #5 clk=~clk;
    reg en=0,we=0,wdata=0;
    reg [7:0] addr=0;
    wire rdata;
    sram_fault_model memory(.*);
    integer seed=0,victim=0,aggressor,initial_state,background,fd,dummy,reads=0;
    string cfg,logfile;
    task write_cell(input integer address_value,input bit data_value);
        begin
            @(negedge clk);en=1;we=1;addr=address_value;wdata=data_value;
            @(negedge clk);en=0;we=0;
        end
    endtask
    task observe(input string phase_name);
        begin
            @(negedge clk);en=1;we=0;addr=victim;
            @(negedge clk);
            if (rdata!==0 && rdata!==1) $fatal(1,"Unknown probe read");
            $fdisplay(fd,"%0d,%0d,%0d,%0d,%0d,%s,%0d",seed,victim,aggressor,
                      initial_state,background,phase_name,rdata);
            reads=reads+1;en=0;
        end
    endtask
    initial begin
        if (!$value$plusargs("CFG=%s",cfg)) $fatal(1,"Missing configuration");
        if (!$value$plusargs("LOG=%s",logfile)) $fatal(1,"Missing probe log");
        dummy=$value$plusargs("SEED=%d",seed);
        dummy=$value$plusargs("VICTIM=%d",victim);
        if (victim<0 || victim>255) $fatal(1,"Bad probe victim");
        fd=$fopen(logfile,"w");
        if (!fd) $fatal(1,"Cannot create probe log");
        $fdisplay(fd,"seed,victim,aggressor,initial,background,phase,actual");
        for(aggressor=0;aggressor<256;aggressor=aggressor+1) if(aggressor!=victim)
            for(initial_state=0;initial_state<2;initial_state=initial_state+1)
                for(background=0;background<2;background=background+1) begin
                    @(negedge clk);en=0;
                    // Trial reset is simulator setup, not a silicon test primitive.
                    // Configuration stays hidden from diagnostic decisions and CSVs.
                    memory.initialize();memory.load_config(cfg);
                    write_cell(aggressor,initial_state);
                    write_cell(victim,background);
                    observe("settle");
                    write_cell(aggressor,1-initial_state);
                    observe("toggle");
                    write_cell(victim,background);
                    observe("rewrite");
                end
        $fclose(fd);
        if(reads!=3060) $fatal(1,"Incomplete probe");
        $display("PASS coupling probe seed=%0d reads=%0d",seed,reads);$finish;
    end
endmodule
