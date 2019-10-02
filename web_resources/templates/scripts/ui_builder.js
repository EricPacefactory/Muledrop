

/*
This script assumes that the following scripts have already been imported:
    "slider_ui.js", "toggle_ui.js", "menu_ui.js", "numentry_ui.js"
*/

// ....................................................................................................................................

// Create a handy lookup dictionary for create UI html
ctrl_html_lookup = {"slider": create_slider_html,
                    "toggle": create_toggle_html,
                    "menu": create_menu_html,
                    "numentry": create_numentry_html};

// Function for inserting the appropriate HTML for each control element, based on the control config dictionary
function create_control_specific_html(single_control_config, initial_settings_dict, sio_ref){
    let control_type = single_control_config["control_type"];
    let control_creation_func = ctrl_html_lookup[control_type];
    return control_creation_func(single_control_config, initial_settings_dict, sio_ref);
}

// ....................................................................................................................................

function create_control_li_html(single_ctrl_dict, initial_settings_dict, sio_ref) {

    // Create control-specific html
    let new_ctrl_html = create_control_specific_html(single_ctrl_dict, initial_settings_dict, sio_ref);

    // If the control html is missing (ex. the control is not set to be visible), return null to indicate no control
    if (new_ctrl_html == null){
        return null;
    }

    // Create a new list-item and add control-specific html into it
    let new_li = document.createElement("li");
    new_li.appendChild(new_ctrl_html);

    // Add an ID to list-item, mainly for debugging so we can access the element using the console if needed...
    let variable_name = single_ctrl_dict["variable_name"];
    new_li.id = "ui_" + variable_name;

    return new_li;
}

// ....................................................................................................................................

// Function for building control groups (i.e. each block of controls which appear on the side of the page)
function create_control_group_html(single_control_group_dict, initial_settings_dict, sio_ref) {

    // Pull out the group name (use as a block title) and the actual list of control definitions
    let control_group_title = single_control_group_dict["group_name"];
    let control_list = single_control_group_dict["control_list"];

    // For debugging:
    console.log("Creating:", control_group_title)

    // Create a div to hold each control group
    let container_div = document.createElement("div");
    container_div.className = "controls_container";

    // Add title to container block
    let container_title = document.createElement("h3");
    container_title.className = "controls_container_title";
    container_title.innerText = control_group_title;

    // Create the ul to wrap control list items
    let control_ul = document.createElement("ul");
    control_ul.className = "controls_ul";

    // Create each control list-item and add to the list
    for(each_control_dict of control_list) {
        let new_control_li = create_control_li_html(each_control_dict, initial_settings_dict, sio_ref);

        // Skip adding this control if the creation function returned null
        if (new_control_li == null){
            continue
        }

        // Add control to control group list
        control_ul.appendChild(new_control_li);
        
        // For debugging
        console.log("  Adding list-item:", new_control_li.id);
        //console.log("APPENDING", new_control_li);

    }

    // Combine the title and list into the containing div
    container_div.appendChild(container_title);
    container_div.appendChild(control_ul);

    return container_div;
}

// ....................................................................................................................................

// Function which creates all of the html to display/interact with controls. Also attaches them to proper spot on the page
function build_all_controls_html_structure(control_specification_list, initial_settings_dict, sio_ref) {

    // Get some handy references
    let control_holder_div = document.getElementById("controls_holder");

    // Make sure we clear out any existing html
    clear_all_controls_html_structure(control_holder_div);

    // Create html for each group of controls and attach to the proper html element for display
    for(each_group of control_specification_list) {
        let new_control_group_html = create_control_group_html(each_group, initial_settings_dict, sio_ref);
        control_holder_div.appendChild(new_control_group_html);
    }
}

// ....................................................................................................................................

function clear_all_controls_html_structure(control_holder_div_ref) {
    while(control_holder_div_ref.firstChild){
        control_holder_div_ref.removeChild(control_holder_div_ref.firstChild);
    }
}

// ....................................................................................................................................
// ....................................................................................................................................