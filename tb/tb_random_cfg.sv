// Optional native constrained random configuration generation on Questa.
module tb_random_cfg;
    import fault_config_pkg::*;
    fault_cfg cfg;
    integer seed=1, count=1, fd, dummy, batch=1, sample_index, random_seed, this_count;
    string filename="random.cfg";
    string sample_filename;
    initial begin
        dummy=$value$plusargs("SEED=%d",seed);
        dummy=$value$plusargs("COUNT=%d",count);
        dummy=$value$plusargs("OUT=%s",filename);
        dummy=$value$plusargs("BATCH=%d",batch);
        if (count<1 || count>3) $fatal(1,"COUNT must be 1..3");
        if (batch<1) $fatal(1,"BATCH must be positive");
        for(sample_index=0;sample_index<batch;sample_index=sample_index+1) begin
            random_seed=seed+sample_index;
            dummy=$urandom(random_seed); cfg=new; cfg.srandom(seed+sample_index);
            this_count=batch==1 ? count : $urandom_range(3,1);
            sample_filename=batch==1 ? filename : $sformatf("%s_%0d.cfg",filename,seed+sample_index);
            fd=$fopen(sample_filename,"w");
            if (!fd) $fatal(1,"Cannot create random configuration");
            $fdisplay(fd,"%0d",this_count);
            repeat(this_count) begin
                if (!cfg.randomize()) $fatal(1,"Randomization failed");
                $fdisplay(fd,"%0d %0d %0d %0d %0d %0d",cfg.kind,cfg.victim,cfg.aggressor,
                          cfg.value,cfg.trigger,cfg.retention_cycles);
            end
            $fclose(fd);
        end
        $finish;
    end
endmodule
