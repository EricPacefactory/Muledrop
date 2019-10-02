
// --------------------------------------------------------------------------------------------------------------------

// Function for sending control updates back to socket server
function socket_control_update(sio_ref, variable_name, new_value, debug = false) {

    let data = {[variable_name]: new_value};
    let json_data = JSON.stringify(data);
    
    if (debug) {
        console.log("POSTING:", data);
        console.log("(JSON)", json_data);
    }

    sio_ref.emit("control_update", json_data);
}

// --------------------------------------------------------------------------------------------------------------------

function get_parent_div(config_data){
    let parent_id = "ui_" + config_data["variable_name"];
    return document.getElementById(parent_id);
}

// --------------------------------------------------------------------------------------------------------------------

function attach_element(parent_element, ui_element_html){
    parent_element.appendChild(ui_element_html);
}

// --------------------------------------------------------------------------------------------------------------------

function truncate_floats(float_value, step_size){
    let decimal_points = Math.round(Math.log10(1/step_size));
    return Number.parseFloat(float_value).toFixed(decimal_points);
}

// --------------------------------------------------------------------------------------------------------------------
// --------------------------------------------------------------------------------------------------------------------
