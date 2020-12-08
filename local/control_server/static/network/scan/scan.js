
// ---------------------------------------------------------------------------------------------------------------------
// Define html/css/url helper functions

// DOM access helpers
const getelem_scan_button = () => document.getElementById("scan_btn_div");
const getelem_results_container = () => document.getElementById("results_container_div");
const getelem_page_back_btn = () => document.getElementById("page_back_btn");
const set_busy_cursor = () => document.body.style.cursor = "wait";
const reset_cursor = () => document.body.style.cursor = "auto";

// Input element access helpers
const getinput_ip_address = () => document.getElementById("ip_address_input");
const getinput_start_range = () => document.getElementById("start_range_input");
const getinput_end_range = () => document.getElementById("end_range_input");

// Route-URL builders
const build_rtsp_scan_url = () => `/control/network/scan-rtsp-ports`;
const redirect_to_url = url => window.location.href = url;


// ---------------------------------------------------------------------------------------------------------------------
// Initial setup

// Global variable used to disable controls after clicking
const GLOBAL = {"controls_enabled": true};

// Attach rtsp scan function to button
const scan_btn_ref = getelem_scan_button();
scan_btn_ref.addEventListener("click", run_scan);


// ---------------------------------------------------------------------------------------------------------------------
// Define functions

// .....................................................................................................................

async function run_scan() {

  // Prevent multiple scans being queued up
  if (GLOBAL.controls_enabled){

    // Communicate scan-in-progress state to user
    show_messages(["Scanning..."]);
    set_to_scan_in_progress();

    // Read inputs
    const scan_data = read_inputs();

    // Bundle post data for connection attempt
    const fetch_args = {method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(scan_data)};

    // Request port scan results (list of open ip addresses) from the server
    let rtsp_scan_json = {};
    try {
        const flask_data_json_str = await fetch(build_rtsp_scan_url(), fetch_args);
        rtsp_scan_json = await flask_data_json_str.json();

    } catch {
        console.log("Error! Couldn't fetch data from server, likely down?");
    }

    // Use response data to update the page
    parse_response(rtsp_scan_json);

    // Undo all 'in-progress' ui changes
    return_from_scan_in_progress();
    console.log("Scan results:", rtsp_scan_json);
  }
}

// .....................................................................................................................

function read_inputs() {

  // Get references to input elements
  const base_ip_ref = getinput_ip_address();
  const start_range_ref = getinput_start_range();
  const end_range_ref = getinput_end_range();

  // Read values
  const ip_value = base_ip_ref.value;
  const start_value = start_range_ref.value;
  const end_value = end_range_ref.value;

  // Bundle everything for return
  const input_data = {"base_ip_address": ip_value,
                      "start_scan_range": start_value,
                      "end_scan_range": end_value}

  return input_data
}

// .....................................................................................................................

function parse_response(rtsp_scan_json) {

  /*
  // FOR DEBUG (generate example ips to display)
  ips = []
  for(let i = 0; i < 30; i++){
    ips[i] = `192.168.0.${i}`;
  }
  rtsp_scan_json = {"scan_success": true, "open_ips_list": ips, "base_ip_address": "auto", "error_msg": null};
  */

  // Unpack the response, with default values (assuming an error by default)
  const default_err_msg = "no response from server";
  const {scan_success = false, open_ips_list = [], base_ip_address = "auto", error_msg = default_err_msg} = rtsp_scan_json;

  // Clear existing scan results
  const scan_results_div = clear_scan_results();

  // Handle error output
  if(!scan_success) {
    show_messages(["*** SCAN ERROR ***", error_msg]);
    return
  }

  // Handle case with no open IPs
  const num_open_ips = (open_ips_list.length);
  const no_open_ips = (num_open_ips === 0);
  if(no_open_ips) {
    show_messages(["Scan complete!", `Used base IP: ${base_ip_address}`, "No IPs found with open RTSP ports"]);
    return
  }  

  // Create a list to display ip addresses
  const new_list_ul = document.createElement("ul");
  new_list_ul.className = "scan_result_ul";
  for(const each_ip of open_ips_list){

    // Create new list item to hold each ip address for display
    const new_li = document.createElement("li");
    new_li.className = "scan_result_ip_li";
    new_li.innerText = each_ip;
    new_list_ul.appendChild(new_li);
  }
  
  // Finally, add the listing back into the scan results element
  scan_results_div.appendChild(new_list_ul);

  return
}

// .....................................................................................................................

function set_to_scan_in_progress() {

  // Disable button clicks
  GLOBAL.controls_enabled = false;

  // Show spinning cursor
  set_busy_cursor();

  // Hide the back button to prevent user from easily leaving the page during scan
  change_back_button_visibility(false);

  return
}

// .....................................................................................................................

function return_from_scan_in_progress() {

  // Re-enable button clicks
  GLOBAL.controls_enabled = true;

  // Reset mouse cursor
  reset_cursor();

  // Show the back button so the user can return to main menu(s)
  change_back_button_visibility(true);
}

// .....................................................................................................................

function show_messages(message_strings) {

  // Clear existing scan results
  const scan_results_div = clear_scan_results();
  
  // Determine if we have a single string or list of strings (display on separate lines)
  const is_single_str = (typeof(message_strings) === "string");
  const message_list = is_single_str ? [message_strings] : message_strings;

  // Add message to scan results holder div
  for(const each_msg of message_list) {
    const new_message_p = document.createElement("p");
    new_message_p.className = "scan_message_p";
    new_message_p.innerText = each_msg;
    scan_results_div.appendChild(new_message_p);
  }

}

// .....................................................................................................................

function clear_scan_results() {

  /* Helper function used to clear existing scan results */

  // Get a reference to the scan results div and remove everything inside
  const results_div = getelem_results_container();
  while(results_div.firstChild){
    results_div.removeChild(results_div.firstChild);
  }

  return results_div
}

// .....................................................................................................................

function change_back_button_visibility(is_visible) {

  /* Helper function used to show/hide the page back button at the bottom of the page */

  // For clarity
  const visibility_setting = is_visible ? "visible" : "hidden";

  // Update the button element
  const btn_ref = getelem_page_back_btn();
  btn_ref.style.visibility = visibility_setting;

  return
}

// .....................................................................................................................
// .....................................................................................................................
