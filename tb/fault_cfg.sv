// Rich configuration for Questa; portable simulator uses the same numeric file format.
package fault_config_pkg;
    typedef enum int {SAF0=1, SAF1=2, TF_UP=3, TF_DOWN=4, CFIN=5,
                      CFID=6, CFST=7, AF=8, ROW=9, COL=10, DRF=11} fault_type;
    class fault_cfg;
        rand fault_type kind;
        rand int victim, aggressor;
        rand bit value, trigger;
        int retention_cycles = 10000;
        constraint valid_addresses {
            victim inside {[0:255]}; aggressor inside {[0:255]};
            if (kind inside {CFIN, CFID, CFST, AF}) victim != aggressor;
        }
        function new(); endfunction
    endclass
endpackage
