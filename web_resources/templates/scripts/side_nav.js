
// --------------------------------------------------------------------------------------------------------------------

function show_hide_options() {

    // Get the ul option list associated with 'this' button
    var self_id = this.id;
    var sub_ul_id = self_id.replace("core_comp_", "core_comp_ul_");
    var sub_ul_ref = document.getElementById(sub_ul_id);

    if (sub_ul_ref.style.display === "none") {
        sub_ul_ref.style.display = "grid";
    } else {
        sub_ul_ref.style.display = "none";
    }

    /*
    console.log("MY ID:", self_id);
    console.log("UL ID:", sub_ul_id);
    console.log("TEsT:", test_ref);
    */
}

// --------------------------------------------------------------------------------------------------------------------

// Attach callbacks to all the nav buttons
var nav_btn_refs = document.getElementsByClassName("core_component_btn");
for(each_btn of nav_btn_refs){
    each_btn.addEventListener("click", show_hide_options);
}

// --------------------------------------------------------------------------------------------------------------------
// --------------------------------------------------------------------------------------------------------------------
