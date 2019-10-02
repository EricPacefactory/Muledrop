
// ....................................................................................................................................

function create_selection_li_html(single_display_dict, sio_ref) {

    // Create new li element to represent the display selection option
    let display_name =  single_display_dict["window_name"];
    let new_li = document.createElement("li");
    new_li.innerText = display_name;

    // Add an ID to list-item, mainly for debugging so we can access the element using the console if needed...
    new_li.id = "ui_ds_" + display_name;

    // Attach display selection callback
    new_li.addEventListener("click", display_selection_callback(sio_ref, display_name));

    return new_li;
}

// ....................................................................................................................................

function build_display_selection_html(display_specification_dict, sio_ref){

    // Get some handy references
    const dispselect_holder_div = document.getElementById("display_selection_list");

    // Make sure we clear out any existing html (e.g. default 'Loading' list item)
    clear_all_display_selection_html(dispselect_holder_div);

    // Extract useful info
    const initial_display = display_specification_dict["initial_display"];
    const display_dict = display_specification_dict["displays"];
    const layout_row_col = display_specification_dict["layout_row_col"];

    // Create a list item for each display entry
    for(each_display of display_dict){
        const new_selection = create_selection_li_html(each_display, sio_ref);
        dispselect_holder_div.appendChild(new_selection);
    }

    // Add a 'grid view' option as long as more than 1 display is available
    if(display_dict.length > 1){
        const fake_display = {"window_name": "Grid View"};
        const grid_selection = create_selection_li_html(fake_display, sio_ref);
        dispselect_holder_div.appendChild(grid_selection);
    }

}

// ....................................................................................................................................

function clear_all_display_selection_html(dispselect_holder_div_ref) {
    while(dispselect_holder_div_ref.firstChild){
        dispselect_holder_div_ref.removeChild(dispselect_holder_div_ref.firstChild);
    }
}

// ....................................................................................................................................

function display_selection_callback(sio_ref, display_name){

    // Awkward trick to use callback args
    return function() {

        // Let the socket server know what's up
        socket_display_update(sio_ref, display_name, true);

    }
}

// ....................................................................................................................................

// Function for sending display selection updates back to socket server
function socket_display_update(sio_ref, display_name, debug = false) {

    let data = {"display_select": display_name};
    let json_data = JSON.stringify(data);
    
    if (debug) {
        console.log("POSTING:", data);
        console.log("(JSON)", json_data);
    }

    sio_ref.emit("display_request", json_data);
}

// ....................................................................................................................................
// ....................................................................................................................................