`timescale 1ns/1ps
// Verification model only. Fixed ordered fault list gives deterministic composition.
module sram_fault_model #(parameter integer N=256, MAX_FAULTS=3) (
    input wire clk, en, we,
    input wire [7:0] addr,
    input wire wdata,
    output reg rdata
);
    bit mem [0:N-1];
    integer written_at [0:N-1];
    bit decayed [0:N-1];
    integer types [0:MAX_FAULTS-1], victims [0:MAX_FAULTS-1];
    integer aggressors [0:MAX_FAULTS-1], values [0:MAX_FAULTS-1];
    integer triggers [0:MAX_FAULTS-1], thresholds [0:MAX_FAULTS-1];
    integer fault_count, cycle;

    task initialize;
        integer i;
        begin
            fault_count=0; cycle=0; rdata=0;
            for (i=0;i<N;i=i+1) begin
                mem[i]=0; written_at[i]=0; decayed[i]=0;
            end
        end
    endtask
    task load_config(input string filename);
        integer fd, rc, k, v, a, val, trig, threshold;
        begin
            fd=$fopen(filename,"r");
            if (!fd) $fatal(1,"Cannot open configuration %s",filename);
            rc=$fscanf(fd,"%d",fault_count);
            if (rc!=1 || fault_count<0 || fault_count>MAX_FAULTS)
                $fatal(1,"Bad fault count");
            for (k=0;k<fault_count;k=k+1) begin
                rc=$fscanf(fd,"%d %d %d %d %d %d",types[k],v,a,val,trig,threshold);
                if (rc!=6 || types[k]<1 || types[k]>11 || v<0 || v>=N || a<0 || a>=N ||
                    val<0 || val>1 || trig<0 || trig>1 || threshold<1)
                    $fatal(1,"Bad fault record %0d",k);
                if (types[k]>=5 && types[k]<=8 && v==a) $fatal(1,"Self coupling/alias");
                victims[k]=v; aggressors[k]=a; values[k]=val;
                triggers[k]=trig; thresholds[k]=threshold;
            end
            $fclose(fd);
        end
    endtask
    function automatic integer physical_address(input integer a);
        integer k, p;
        begin
            p=a;
            for (k=0;k<fault_count;k=k+1)
                if (types[k]==8 && a==victims[k]) p=aggressors[k];
            physical_address=p;
        end
    endfunction
    function automatic bit apply_state_faults(input integer now_cycle);
        integer k;
        begin
            for (k=0;k<fault_count;k=k+1) begin
                if (types[k]==11 && !decayed[victims[k]] &&
                    now_cycle-written_at[victims[k]]>=thresholds[k]) begin
                    mem[victims[k]]=~mem[victims[k]]; decayed[victims[k]]=1;
                end
                if (types[k]==7 && mem[aggressors[k]]==triggers[k])
                    mem[victims[k]]=values[k];
            end
            apply_state_faults=0;
        end
    endfunction
    function automatic bit do_write(input integer a, input bit data, input integer now_cycle);
        integer p,k;
        bit old, next_value, unused;
        begin
            unused=apply_state_faults(now_cycle); p=physical_address(a);
            old=mem[p]; next_value=data;
            for (k=0;k<fault_count;k=k+1) if (p==victims[k]) begin
                if (types[k]==3 && old==0 && data==1) next_value=old;
                if (types[k]==4 && old==1 && data==0) next_value=old;
            end
            mem[p]=next_value; written_at[p]=now_cycle; decayed[p]=0;
            for (k=0;k<fault_count;k=k+1) if (p==aggressors[k] && old!=next_value) begin
                if (types[k]==5) mem[victims[k]]=~mem[victims[k]];
                if (types[k]==6 && next_value==triggers[k]) mem[victims[k]]=values[k];
            end
            unused=apply_state_faults(now_cycle); do_write=0;
        end
    endfunction
    function automatic bit do_read(input integer a, input integer now_cycle);
        integer p,k;
        bit data, unused;
        begin
            unused=apply_state_faults(now_cycle); p=physical_address(a); data=mem[p];
            for (k=0;k<fault_count;k=k+1) begin
                if (p==victims[k] && types[k]==1) data=0;
                if (p==victims[k] && types[k]==2) data=1;
                if (types[k]==9 && p/16==victims[k]/16) data=values[k];
                if (types[k]==10 && p%16==victims[k]%16) data=values[k];
            end
            do_read=data;
        end
    endfunction
    initial initialize();
    always @(posedge clk) begin
        cycle=cycle+1;
        if (en) begin
            if (we) begin : write_block
                bit ignored;
                ignored=do_write(addr,wdata,cycle);
            end else rdata <= do_read(addr,cycle);
        end
    end
endmodule
