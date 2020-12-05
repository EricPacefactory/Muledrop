
// ---------------------------------------------------------------------------------------------------------------------
// Define html/css/url helper functions

// DOM access helpers
const getelem_connect_button = () => document.getElementById("connect_btn_div");
const getelem_status_message = () => document.getElementById("connect_status_div");
const getelem_image_container = () => document.getElementById("connect_image_div");
const getelem_video_info_message = () => document.getElementById("source_info_div");
const set_busy_cursor = () => document.body.style.cursor = "wait";
const reset_cursor = () => document.body.style.cursor = "auto";

// Input element access helpers
const getinput_ip_address = () => document.getElementById("ip_address_input");
const getinput_route = () => document.getElementById("route_input");
const getinput_username = () => document.getElementById("username_input");
const getinput_password = () => document.getElementById("password_input");

// Route-URL builders
const build_rtsp_connect_url = () => `/control/network/test-camera-connect`;
const redirect_to_url = url => window.location.href = url;


// ---------------------------------------------------------------------------------------------------------------------
// Initial setup

// Global variable used to disable controls after clicking
const GLOBAL = {"controls_enabled": true};

// Attach rtsp connect function to button
const connect_btn_ref = getelem_connect_button();
connect_btn_ref.addEventListener("click", test_camera_connection);


// ---------------------------------------------------------------------------------------------------------------------
// Define functions

// .....................................................................................................................

async function test_camera_connection() {

  // Prevent multiple connection attempts being queued up
  if (GLOBAL.controls_enabled){
    
    // Communicate connect-in-progress state to user
    update_status_text("Connecting...");
    set_to_connect_in_progress();

    // Read inputs
    const connection_data = read_inputs();

    // Bundle post data for connection attempt
    const fetch_args = {method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(connection_data)};

    // Get camera connection results from the server
    let rtsp_connect_json = {};
    try {
        const flask_data_json_str = await fetch(build_rtsp_connect_url(), fetch_args);
        rtsp_connect_json = await flask_data_json_str.json();

    } catch {
        console.log("Error! Couldn't fetch data from server, likely down?");
    }

    // Use response data to update the page
    parse_response(rtsp_connect_json);

    // Undo all 'in-progress' ui changes
    return_from_connect_in_progress();
    console.log("Connect results:", rtsp_connect_json);
  }
}

// .....................................................................................................................

function read_inputs() {

  // Get references to input elements
  const ip_ref = getinput_ip_address();
  const route_ref = getinput_route();
  const username_ref = getinput_username();
  const password_ref = getinput_password();

  // Read values
  const ip_value = ip_ref.value;
  const route_value = route_ref.value;
  const username_value = username_ref.value;
  const password_value = password_ref.value;

  // Bundle everything for return
  const input_data = {"ip_address": ip_value,
                      "route": route_value,
                      "username": username_value,
                      "password": password_value}

  return input_data
}

// .....................................................................................................................

function parse_response(rtsp_connect_response_json) {

  // Unpack the response, with default values (assuming an error by default)
  const default_err_msg = "no response from server";
  const {connect_success = false, b64_jpg = null, video_source_info = null, error_msg = default_err_msg} = rtsp_connect_response_json;

  // Update status message to indicate success/failure
  const status_success_msg = "Connection succeeded!";
  const status_error_msg = `Error: ${error_msg}`;
  const status_msg = connect_success ? status_success_msg : status_error_msg;
  update_status_text(status_msg);

  // Update video info if possible
  const {width = 0, height = 0, framerate = 0, codec = "unknown"} = video_source_info;
  const video_info_success_msg = `(${codec} - ${width}x${height} @ ${framerate} fps)`;
  const video_info_error_msg = "";
  const video_info_msg = connect_success ? video_info_success_msg : video_info_error_msg;
  update_video_info(video_info_msg);

  // Update displayed image
  update_display_image(b64_jpg);

  return
}

// .....................................................................................................................

function set_to_connect_in_progress() {

  // Disable button clicks
  GLOBAL.controls_enabled = false;

  // Show spinning cursor
  set_busy_cursor();
}

// .....................................................................................................................

function return_from_connect_in_progress() {

  // Re-enable button clicks
  GLOBAL.controls_enabled = true;

  // Reset mouse cursor
  reset_cursor();
}

// .....................................................................................................................

function update_status_text(status_msg) {

  // Replace status message with new text
  const status_ref = getelem_status_message();
  status_ref.innerText = status_msg;

  return
}

function update_video_info(video_info_msg) {

  // Replace video info message with new text
  const video_info_ref = getelem_video_info_message();
  video_info_ref.innerText = video_info_msg;

  return
}

// .....................................................................................................................

function update_display_image(b64_jpg_data) {

  // Clear whatever is currently in the image div
  const image_container_ref = getelem_image_container();
  while(image_container_ref.firstChild){
    image_container_ref.removeChild(image_container_ref.firstChild);
  }

  // Either display new image data, or indicate data is missing
  const no_image = (b64_jpg_data === null)
  if (no_image) {

    // Add text to indicate missing image data
    const image_is_missing_text = document.createElement("p");
    image_is_missing_text.innerText = "no image data";
    image_container_ref.appendChild(image_is_missing_text);

  } else {

    // Place b64 jpg into image element
    const img_elem = document.createElement("img");
    img_elem.src = `data:image/jpeg;base64,${b64_jpg_data}`;
    image_container_ref.appendChild(img_elem);

  }

  return no_image
}

// .....................................................................................................................
// .....................................................................................................................
