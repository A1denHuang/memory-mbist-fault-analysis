module mbist_coverage(input logic clk, rst_n, en, stop_on_fail, fail_valid,
                     input logic [7:0] addr, fail_addr,
                     input logic [2:0] element, fail_element,
                     input integer fault_kind, address_order);
    covergroup operation_cg @(posedge clk iff (rst_n && en));
        elements: coverpoint element { bins march[]={[0:5]}; }
        modes: coverpoint stop_on_fail;
        boundary: coverpoint addr {
            bins first={0}; bins last={255};
            bins row_start[]={16,32,48,64,80,96,112,128,144,160,176,192,208,224,240};
            bins row_end[]={15,31,47,63,79,95,111,127,143,159,175,191,207,223,239};
            bins interior=default;
        }
        element_mode: cross elements,modes;
    endgroup
    // Only attribute a failure to an injection in single-fault experiments.
    covergroup fault_cg @(negedge clk iff (rst_n && fail_valid && fault_kind>0));
        kind: coverpoint fault_kind { bins faults[]={[1:11]}; }
        detected_in: coverpoint fail_element { bins reads[]={[1:5]}; }
        ordering: coverpoint address_order { bins lower_address={0}; bins higher_address={1}; bins other={2}; }
        fault_element: cross kind,detected_in;
        coupling_order: cross kind,ordering;
    endgroup
    operation_cg operations=new;
    fault_cg faults=new;
endmodule
