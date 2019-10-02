
// --------------------------------------------------------------------------------------------------------------------
// See ui_shared.js for a number of functions called here!
// --------------------------------------------------------------------------------------------------------------------

function toggle_callback(sio_ref){

    // Awkward trick to use callback args
    return function() {

        // Get element IDs so we can get values and update text
        var variable_name = this.id;
        var curr_state = this.checked;

        // Let the socket server know what's up
        socket_control_update(sio_ref, variable_name, curr_state);

        // Debugging
        //console.log("TOGGLE" + this.id, curr_state);
    }
}

// --------------------------------------------------------------------------------------------------------------------

function create_toggle_html(config_data, initial_config_dict, sio_ref){

    // Pull out the relevant configuration data
    var { label, variable_name, visible } = config_data;
    var initial_value = initial_config_dict[variable_name];

    // Don't return any html if the control is not supposed to be visible
    if (!visible){
        return null;
    }

    // Create div to hold the full toggle UI object
    var wrappper_elem = document.createElement("div");
    wrappper_elem.className = "toggle_wrapper";

    // Create (bold) label text for the toggle
    var label_elem = document.createElement("label");
    label_elem.innerHTML = "<b>" + label + ": </b>";

    // Create a label wrapper so we cna click on the whole toggle button
    var toggle_label_wrapper_elem = document.createElement("label");
    toggle_label_wrapper_elem.className = "toggle_switch";

    // Add checkbox for actual toggle functionality
    var toggle_checkbox_elem = document.createElement("input");
    toggle_checkbox_elem.type = "checkbox";
    toggle_checkbox_elem.id = variable_name;
    toggle_checkbox_elem.checked = Boolean(initial_value);

    // Attach toggle callback
    toggle_checkbox_elem.addEventListener("input", toggle_callback(sio_ref));
    
    // Add 'slider' graphics for the toggle button
    var toggle_span_elem = document.createElement("span");
    toggle_span_elem.className = "toggle_span";

    // Build the full element
    toggle_label_wrapper_elem.appendChild(toggle_checkbox_elem);
    toggle_label_wrapper_elem.appendChild(toggle_span_elem);
    wrappper_elem.appendChild(label_elem);
    wrappper_elem.appendChild(toggle_label_wrapper_elem);
    return wrappper_elem;
}

// --------------------------------------------------------------------------------------------------------------------
// --------------------------------------------------------------------------------------------------------------------
