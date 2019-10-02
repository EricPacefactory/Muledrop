
// --------------------------------------------------------------------------------------------------------------------
// See ui_shared.js for a number of functions called here!
// --------------------------------------------------------------------------------------------------------------------

function slider_callback(sio_ref){
    
    // Awkward trick to use callback args
    return function() {
        // Get element IDs so we can get values and update text
        let variable_name = this.id;
        let output_txt_id = "ui_output_" + variable_name;
        let new_slider_value_str = document.getElementById(variable_name).value;
        let new_slider_value_float = parseFloat(new_slider_value_str);
        let new_slider_value_trunc = truncate_floats(new_slider_value_float, this.step);

        // Update the output display text
        document.getElementById(output_txt_id).innerText = new_slider_value_trunc;

        // Let the socket server know what's up
        socket_control_update(sio_ref, variable_name, new_slider_value_float);

        // Debugging
        //console.log("SLIDER" + this.id);
    }
}

// --------------------------------------------------------------------------------------------------------------------

function create_slider_html(config_data, initial_config_dict, sio_ref){

    // Pull out the relevant configuration data
    let { label, min_value, max_value, step_size, variable_name, visible, return_type } = config_data;
    let initial_value = initial_config_dict[variable_name];

    // Don't return any html if the control is not supposed to be visible
    if (!visible){
        return null;
    }

    // Create div to hold the full slider UI object
    let wrappper_elem = document.createElement("div");
    wrappper_elem.className = "slider_wrapper";

    // Create div to hold the slider label and output value label
    let label_wrapper = document.createElement("div");
    label_wrapper.className = "slider_label_wrapper";

    // Create (bold) label text for the slider
    let label_elem = document.createElement("label");
    label_elem.innerHTML = "<b>" + label + ": </b>";

    // Add a value display next to the slider label
    let output_label_elem = document.createElement("label");
    output_label_elem.id = "ui_output_" + variable_name;
    output_label_elem.style.textAlign = "right";

    // Create range element and set parameters
    let input_elem = document.createElement("input");
    input_elem.type = "range";
    input_elem.max = max_value;
    input_elem.min = min_value;
    input_elem.step = step_size;
    input_elem.value = initial_value;
    input_elem.className = "slider";
    input_elem.id = variable_name;

    // Set initial output value display
    output_label_elem.innerText = truncate_floats(initial_value, step_size);

    // Attach slider callback
    input_elem.addEventListener("input", slider_callback(sio_ref));

    // Build the full slider html element
    label_wrapper.appendChild(label_elem);
    label_wrapper.appendChild(output_label_elem);
    wrappper_elem.appendChild(label_wrapper);
    wrappper_elem.appendChild(input_elem);

    return wrappper_elem;
}

// --------------------------------------------------------------------------------------------------------------------
// --------------------------------------------------------------------------------------------------------------------

