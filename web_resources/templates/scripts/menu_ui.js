
// --------------------------------------------------------------------------------------------------------------------
// See ui_shared.js for a number of functions called here!
// --------------------------------------------------------------------------------------------------------------------

function menu_callback(sio_ref, option_value_list){

    // Awkward trick to use callback args
    return function() {
        // Get element IDs so we can get values and update text
        let variable_name = this.id;
        let current_idx = this.selectedIndex;
        let new_menu_value = option_value_list[current_idx];

        // Let the socket server know what's up
        socket_control_update(sio_ref, variable_name, new_menu_value);

        // Debugging
        //console.log("MENU:", new_menu_value);
    }
}

// --------------------------------------------------------------------------------------------------------------------

function create_menu_html(config_data, initial_config_dict, sio_ref){

    // Pull out the relevant configuration data
    let { label, variable_name, option_label_value_list, visible } = config_data;
    let initial_value = initial_config_dict[variable_name];

    // Don't return any html if the control is not supposed to be visible
    if (!visible){
        return null;
    }

    // Create div to hold the full menu UI object
    let wrappper_elem = document.createElement("div");
    wrappper_elem.className = "menu_wrapper";

    // Create (bold) label text for the slider
    let label_elem = document.createElement("label");
    label_elem.innerHTML = "<b>" + label + ": </b>";

    // Create select element
    let select_elem = document.createElement("select");
    select_elem.id = variable_name;
    select_elem.className = "menu_select";

    // Split labels/values into separate lists for convenience
    const option_label_list = option_label_value_list.map(each_tuple => each_tuple[0]);
    const option_value_list = option_label_value_list.map(each_tuple => each_tuple[1]);
    // Add option labels the selection (menu) element
    option_label_list.forEach(each_label => {

        // Create a new option label to add to the menu
        var new_option = document.createElement("option");
        new_option.innerText = each_label;
        select_elem.appendChild(new_option);
    });

    // Set the finished menu control to the correct initial value
    const initial_value_index = option_value_list.indexOf(initial_value);
    select_elem.selectedIndex = initial_value_index;

    // Attach menu callback
    select_elem.addEventListener("input", menu_callback(sio_ref, option_value_list));

    // Build full menu UI element
    wrappper_elem.appendChild(label_elem);
    wrappper_elem.appendChild(select_elem);

    return wrappper_elem;
}

// --------------------------------------------------------------------------------------------------------------------
// --------------------------------------------------------------------------------------------------------------------
