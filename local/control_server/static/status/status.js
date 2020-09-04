
// ---------------------------------------------------------------------------------------------------------------------
// Define html/css/url helper functions

// DOM access helpers
const getelem_main_container = () => document.getElementById("main_container");
const getelems_img_buttons = () => Array.from(document.getElementsByClassName("img_button"));
const set_loading_cursor = () => document.body.style.cursor = "wait";

// Route-URL builders
const build_camera_status_request_url = () => `/status/get-cameras-status`;
const build_camera_autolaunch_url = (camera_name, enable_autolaunch) => `/control/cameras/autolaunch/${camera_name}/${enable_autolaunch}`; 
const build_camera_start_url = camera_name => `/control/cameras/start/${camera_name}`;
const build_camera_stop_url = camera_name => `/control/cameras/stop/${camera_name}`;
const redirect_to_url = url => window.location.href = url;

// Resource-URL builders
const build_auto_off_icon_url = () => `/status/icons/infinite_grey_icon.svg`;
const build_auto_on_icon_url = () => `/status/icons/infinite_gold_icon.svg`;
const build_start_icon_url = () => `/status/icons/up_icon.svg`;
const build_stop_icon_url = () => `/status/icons/down_icon.svg`;


// ---------------------------------------------------------------------------------------------------------------------
// Initial setup

// Global variable used to disable controls after clicking one
const GLOBAL = {"controls_enabled": true};

// Make initial request for data needed to generate UI
update_camera_status_ui();


// ---------------------------------------------------------------------------------------------------------------------
// Define functions

// .....................................................................................................................

async function update_camera_status_ui() {

    // Get camera status data from the server
    let status_json_data = {};
    try {
        const flask_data_json_str = await fetch(build_camera_status_request_url());
        status_json_data = await flask_data_json_str.json();

    } catch {
        console.log("Error! Couldn't fetch data from server, likely down?");
        return
    }

    // Print out data in console for debugging
    console.log("Got data:", status_json_data);

    // (Re-)Build the camera status UI elements
    generate_ui(status_json_data);

    // Decide how long we should wait to re-call this function, based on whether camera status is likely to update soon
    const reduce_update_delay = check_need_to_reduce_update_delay(status_json_data);
    const ms_to_wait = 1000 * (reduce_update_delay ? 10 : 30);
    window.setTimeout(update_camera_status_ui, ms_to_wait);
}

// .....................................................................................................................

function check_need_to_reduce_update_delay(status_json_data){

    // Initialize output
    let reduce_update_delay = false;

    // We should reduce the page update delay if any camera is in standby or reconnecting
    const camera_status_entries_array = Object.values(status_json_data);
    for(each_camera_status of camera_status_entries_array) {
        const camera_in_standby = (each_camera_status["in_standby"]);
        const camera_reconnecting = (each_camera_status["autolaunch_enabled"] && !each_camera_status["is_online"]);
        reduce_update_delay = camera_in_standby || camera_reconnecting;
        if(reduce_update_delay){
            break;
        }
    }

    return reduce_update_delay
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
        const new_elem = create_one_camera_ui(each_camera_name, each_camera_status);
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

function create_one_camera_ui(camera_name, camera_status_dict) {

    // Pull out camera status info (formatting is set by python code!)
    const {is_online, in_standby, autolaunch_enabled, description, timestamp_str} = camera_status_dict;

    // Set up some derived values, based on status info
    const inactive_style = "camera_offline";
    const active_style = in_standby ? "camera_standby" : "camera_online";
    const camera_status_style = is_online ? active_style : inactive_style;
    const fully_online = is_online && !in_standby;
    const description_text = fully_online ? timestamp_str : description;

    // Create parent container to hold status info + control icons
    const new_camera_container = document.createElement("div");
    new_camera_container.className = "camera_container_div";

    // .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .

    // Create div which holds the auto-launch on/off icon
    const auto_btn_url = build_camera_autolaunch_url(camera_name, !autolaunch_enabled);
    const new_auto_btn = document.createElement("div");
    new_auto_btn.className = "img_button";
    new_auto_btn.addEventListener("click", callback_control_button(auto_btn_url));
    const new_auto_icon = document.createElement("img");
    new_auto_icon.src = autolaunch_enabled ? build_auto_on_icon_url() : build_auto_off_icon_url();
    new_auto_icon.alt = "A";
    new_auto_btn.appendChild(new_auto_icon);

    // .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .

    // Create div which acts as parent container for the name & time
    const new_status_div = document.createElement("div");
    new_status_div.className = "camera_status_div";
    new_status_div.classList.add(camera_status_style);

    // Create div which holds the camera name
    const camera_name_with_spaces = camera_name.replace(/_/g, " ");
    const new_name_div = document.createElement("div");
    new_name_div.className = "camera_name_div";
    new_name_div.innerText = camera_name_with_spaces;

    // Create div which holds the camera start time info
    const new_time_div = document.createElement("div");
    new_time_div.className = "camera_time_div";
    new_time_div.innerText = description_text;

    // Put the status elements together
    new_status_div.appendChild(new_name_div);
    new_status_div.appendChild(new_time_div);

    // .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .

    // Figure out button resources, based on camera online status
    let start_stop_btn_url = "";
    let start_stop_btn_icon_url = "";
    let start_stop_btn_alt_str = "";
    if (is_online) {
        start_stop_btn_url = build_camera_stop_url(camera_name);
        start_stop_btn_icon_url = build_stop_icon_url();
        start_stop_btn_alt_str = "off";

    } else {
        start_stop_btn_url = build_camera_start_url(camera_name);
        start_stop_btn_icon_url = build_start_icon_url();
        start_stop_btn_alt_str = "on";
    }

    // Create holder for camera start/stop button
    const new_start_stop_btn = document.createElement("div");
    new_start_stop_btn.className = "img_button";
    new_start_stop_btn.addEventListener("click", callback_control_button(start_stop_btn_url));
    const new_start_stop_icon = document.createElement("img");
    new_start_stop_icon.src = start_stop_btn_icon_url;
    new_start_stop_icon.alt = start_stop_btn_alt_str;
    new_start_stop_btn.appendChild(new_start_stop_icon);

    // .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .

    // Finally, put the status & control icons together
    new_camera_container.appendChild(new_auto_btn);
    new_camera_container.appendChild(new_status_div);
    new_camera_container.appendChild(new_start_stop_btn);

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

function callback_control_button(button_url){

    function inner_callback() {

        // Prevent multiple control commands being queued up
        if (GLOBAL.controls_enabled){

            // Set the cursor to a loading indicator & disable the buttons while waiting
            set_loading_cursor();
            disable_control_buttons();

            // Handle controls by sending the page to a specifc url so the server can figure out what to do
            redirect_to_url(button_url);
        }
    }

    return inner_callback
}

// .....................................................................................................................

function disable_control_buttons() {

    // Disable future control button clicks
    GLOBAL.controls_enabled = false;

    // Change button aesthetics to show buttons are disabled
    const img_button_array = getelems_img_buttons();
    for(const each_img_btn of img_button_array){
        each_img_btn.className = "disabled_img_button";
    }

}

// .....................................................................................................................
// .....................................................................................................................


// ---------------------------------------------------------------------------------------------------------------------
// Scrap


