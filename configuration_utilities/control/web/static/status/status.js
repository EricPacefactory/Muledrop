
// ---------------------------------------------------------------------------------------------------------------------
// Define html/css/url helper functions

// DOM access helpers
const getelem_main_container = () => document.getElementById("main_container");
const getelems_img_buttons = () => Array.from(document.getElementsByClassName("img_button"));
const set_loading_cursor = () => document.body.style.cursor = "wait";

// Route-URL builders
const build_camera_status_request_url = () => `/status/cameras`;
const build_camera_restart_url = camera_name => `/control/restart/${camera_name}`;
const build_camera_stop_url = camera_name => `/control/stop/${camera_name}`;
const redirect_to_url = url => window.location.href = url;

// Resource-URL builders
const build_auto_off_icon_url = () => `/status/icons/auto_off_icon.svg`;
const build_auto_on_icon_url = () => `/status/icons/auto_on_icon.svg`;
const build_restart_icon_url = () => `/status/icons/restart_icon.svg`;
const build_stop_icon_url = () => `/status/icons/stop_icon.svg`;


// ---------------------------------------------------------------------------------------------------------------------
// Initial setup

// Global variable used to disable controls after clicking one
const glb = {"controls_enabled": true};

// Make initial request for data needed to generate UI
update_camera_status_ui();


// ---------------------------------------------------------------------------------------------------------------------
// Define functions

// .....................................................................................................................

function update_camera_status_ui() {

    // Set the repeat frequency for updating the camera status UI elements
    const repeat_every_n_sec = 30;

    // Make requests to the flask server for camera status
    fetch(build_camera_status_request_url())
    .then(flask_data_json_str => flask_data_json_str.json())
    .then(debug_response)
    .then(generate_ui)
    .then(delay_function_call(update_camera_status_ui, repeat_every_n_sec))
    .catch(error => console.error("Setup error:", error))
}

// .....................................................................................................................

function debug_response(status_json_data) {

    // Some feedback
    console.log("Got data:", status_json_data);

    return status_json_data
}

// .....................................................................................................................

function generate_ui(status_json_data) {

    // Get a reference to the main container so can append each new camera UI to it
    const container_ref = getelem_main_container();

    // Clear anything currently in the container
    while(container_ref.firstChild){
        container_ref.removeChild(container_ref.firstChild);
    }
    
    // Loop over every camera entry and create corresponding UI elements
    const status_items = Object.entries(status_json_data);
    for(const [each_camera_name, each_camera_status] of status_items){
        const {is_online, start_timestamp_str} = each_camera_status;
        const new_elem = create_one_camera_ui(each_camera_name, is_online, start_timestamp_str)
        container_ref.appendChild(new_elem)
    }

    // If there aren't any camera entries, add a special indicator for better user feedback
    const no_cameras = (status_items.length == 0);
    if (no_cameras) {
        const no_cameras_elem = create_no_cameras_ui();
        container_ref.appendChild(no_cameras_elem);
    }

    return status_json_data
}

// .....................................................................................................................

function create_one_camera_ui(camera_name, is_online, start_timestamp_str) {

    // Create parent container to hold status info + control icons
    const new_camera_container = document.createElement("div");
    new_camera_container.className = "camera_container_div";

    /*
    // Create div which holds the auto-launch on/off icon
    const new_auto_div = document.createElement("div");
    new_auto_div.className = "camera_auto_div";
    const new_auto_btn = document.createElement("div");
    new_auto_btn.className = "img_button";
    const new_auto_icon = document.createElement("img");
    new_auto_icon.src = build_auto_on_icon_url();
    new_auto_icon.alt = "A";

    // Add the icon to the div container
    new_auto_btn.appendChild(new_auto_icon);
    new_auto_div.appendChild(new_auto_btn);
    */

    // Create div which acts as parent container for the name & time
    const new_status_div = document.createElement("div");
    new_status_div.className = "camera_status_div";
    new_status_div.classList.add(is_online ? "camera_online" : "camera_offline");

    // Create div which holds the camera name
    const new_name_div = document.createElement("div");
    new_name_div.className = "camera_name_div";
    new_name_div.innerText = camera_name.replace(/_/g, " ");

    // Create div which holds the camera start time info
    const new_time_div = document.createElement("div");
    new_time_div.className = "camera_time_div";
    new_time_div.innerText = is_online ? start_timestamp_str : "Offline";

    // Put the status elements together
    new_status_div.appendChild(new_name_div);
    new_status_div.appendChild(new_time_div);


    // Create control icons
    const new_ctrl_div = document.createElement("div");
    new_ctrl_div.className = "camera_ctrl_div";

    // Create holder for camera restart button
    const new_restart_btn = document.createElement("div");
    new_restart_btn.className = "img_button";
    const new_restart_icon = document.createElement("img");
    new_restart_icon.src = build_restart_icon_url()
    new_restart_icon.alt = "R";
    new_restart_btn.appendChild(new_restart_icon);
    new_restart_btn.addEventListener("click", callback_restart_camera(camera_name));

    // Create holder for camera stop button
    const new_stop_btn = document.createElement("div");
    new_stop_btn.className = "img_button";
    const new_stop_icon = document.createElement("img");
    new_stop_icon.src = build_stop_icon_url()
    new_stop_icon.alt = "X";
    new_stop_btn.appendChild(new_stop_icon);
    new_stop_btn.addEventListener("click", callback_stop_camera(camera_name));
    
    // Put the control elements together
    new_ctrl_div.appendChild(new_restart_btn);
    new_ctrl_div.appendChild(new_stop_btn);

    // Finally, put the status & control icons together
    //new_camera_container.appendChild(new_auto_div);
    new_camera_container.appendChild(new_status_div);
    new_camera_container.appendChild(new_ctrl_div);

    return new_camera_container
}

// .....................................................................................................................

function create_no_cameras_ui() {

    // Create parent container to hold the 'no cameras' ui elements
    const new_warning_container = document.createElement("div");
    new_warning_container.className = "no_cameras_warning_div";

    // Create warning messages
    const new_text_row_1 = document.createElement("p");
    new_text_row_1.className = "no_cameras_p";
    new_text_row_1.innerText = "No cameras!";

    // Add warning text to the warning container
    new_warning_container.appendChild(new_text_row_1);

    return new_warning_container
}

// .....................................................................................................................

function callback_restart_camera(camera_name) {

    function inner_callback_restart_camera() {

        // Prevent multiple control commands being queued up
        if (glb.controls_enabled){

            // Set the cursor to a loading indicator & disable the buttons while waiting
            set_loading_cursor()
            disable_control_buttons();

            // Handle controls by sending the page to a specifc url so the server can figure out what to do
            redirect_to_url(build_camera_restart_url(camera_name));
        }
    }

    return inner_callback_restart_camera
}

// .....................................................................................................................

function callback_stop_camera(camera_name) {
    
    function inner_callback_stop_camera() {

        // Prevent multiple control commands being queued up
        if (glb.controls_enabled){

            // Set the cursor to a loading indicator & disable the buttons while waiting
            set_loading_cursor();
            disable_control_buttons();

            // Handle controls by sending the page to a specifc url so the server can figure out what to do
            redirect_to_url(build_camera_stop_url(camera_name));
        }
    }

    return inner_callback_stop_camera
}


// .....................................................................................................................

function disable_control_buttons() {

    // Disable future control button clicks
    glb.controls_enabled = false;

    // Change button aesthetics to show buttons are disabled
    const img_button_array = getelems_img_buttons();
    for(const each_img_btn of img_button_array){
        each_img_btn.className = "disabled_img_button";
    }

}

// .....................................................................................................................

function delay_function_call(function_to_call, seconds_to_wait) {

    // This function is used to call a function after a delay
    // Intended to be used inside fetch/.then/.then etc. sequence
    // --> Uses timeout (instead of interval) to make sure calls are always sequential
    const ms_to_wait = seconds_to_wait * 1000;
    function inner_delay_function_call(status_json_data) {
        window.setTimeout(function_to_call, ms_to_wait);
        return status_json_data
    }

    return inner_delay_function_call
}

// .....................................................................................................................
// .....................................................................................................................


// ---------------------------------------------------------------------------------------------------------------------
// Scrap

// TODOs
// - Add auto-restart controls for each camera
