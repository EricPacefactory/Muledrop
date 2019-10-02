
// ------------------------------------------------
// Flask provides variables for socket connection:
// flask_socket_url = "http://ip_address:port"
// Use this to set up socket connection
// ------------------------------------------------

// Set up socketio connection
const sio = io(flask_socket_url, { autoConnect: false });
const sio_max_connection_attempts = 10;
var sio_connect_count = 0;

// Store flask data in globals for easier debugging
var initial_control_settings_dict = null;
var control_specification_list = null;
var display_specification_dict = null;
console.log("**************************************");
console.log("SOCKET URL:", flask_socket_url);
console.log("Debugging variables from Flask:");
console.log("  initial_control_settings_dict");
console.log("  control_specification_list");
console.log("  display_specification_dict");
console.log("**************************************");

// ....................................................................................................................................

// Function called when client connects. Trigger configuration request and frame data request
//      Note 1: Configuration data is used to build UI html. It should only be called once.
//      Note 2: The server enters a frame_response loop after receiving a single frame_request message (again, only call once).
sio.on('connect', function(socket){
    console.log("CLIENT CONNECT");

    // Reset connection count to avoid future timeouts, then request config/frame data from the python socket server
    sio_connect_count = 0;
    let dummy_data = JSON.stringify({"CONFIG_REQUEST": true});
    sio.emit("config_request", dummy_data);
    sio.emit("frame_request", dummy_data);
});

// ....................................................................................................................................

// Function called on connection attempt timeout. Allow this to happen a few times before stopping connection attemps completely
sio.on("connect_error", function(err) {
    console.log("SOCKET ERROR - Server not ready?");
    sio_connect_count += 1;
    if (sio_connect_count > sio_max_connection_attempts) {
        console.log("CONNECTION FAILED!");
        console.log("Closing socket...");
        sio.close();
    }
});

// ....................................................................................................................................

// VERY IMPORTANT: Function called when receiving response to config_request. Sets up the UI!
sio.on("config_response", function(all_config_data) {
    console.log("CONFIG RESPONSE:", all_config_data);

    // Extract config data into more meaningful variables
    control_specification_list = all_config_data["control"];
    initial_control_settings_dict = all_config_data["initial"];
    display_specification_dict = all_config_data["display"];

    // Dynamically set up the UI elements based on the config (control & initial values) specification
    build_all_controls_html_structure(control_specification_list, initial_control_settings_dict, sio);

    // Set up display
    build_display_selection_html(display_specification_dict, sio);
    //build_display_selection_html(display_specification_dict, sio);
    //let image_div = document.getElementById("image_div");
});

// ....................................................................................................................................

// Function called when receiving response to frame_request. Used to update image display in page
// TEMPORARY: Very high network/CPU load! Should replace with WebRTC/RTSP connection. Requires python RTSP server
sio.on("frame_response", function(data) {
    //console.log("FRAME RESPONSE", data);
    let img_ref = document.getElementById("disp_image");
    img_ref.src = data["frame_b64_str"];
    //let timing_data = data["stage_timing"];
    //console.log(timing_data)
});

// Only try to connect the socket if a valid url was given
if(flask_socket_url != ""){
    sio.open();
} else {
    console.log("SOCKET NOT OPENED. BAD URL!", flask_socket_url);
}

// ....................................................................................................................................

// Function for handling configuration saving
function save_config_callback(sio_ref, debug = false) {

    return function() {

        let dummy_data = JSON.stringify({"SAVE_REQUEST": true});
        sio_ref.emit("save_request", dummy_data);

        if (debug) {
            console.log("SAVE REQUEST:", dummy_data);
        }
    }

}

// Attach callback to the save button
document.getElementById("core_save_button").addEventListener("click", save_config_callback(sio, true));

// Attach function to disconnect on page change/refresh
window.onbeforeunload = function(event) {
    ///event.returnValue = "Write something clever here..";
    sio.disconnect();
  };
//window.addEventListener("onbeforeunload", sio.disconnect);

// ....................................................................................................................................
// ....................................................................................................................................
