
// ---------------------------------------------------------------------------------------------------------------------
// Define html/css/url helper functions

// DOM access helpers
const getelem_scan_results = () => document.getElementById("scan_results_div");
const getelem_page_back_btn = () => document.getElementById("page_back_btn");
const set_busy_cursor = () => document.body.style.cursor = "wait";
const reset_cursor = () => document.body.style.cursor = "auto";

// Route-URL builders
const build_rtsp_scan_url = () => `/control/network/scan-rtsp-ports`;
const redirect_to_url = url => window.location.href = url;


// ---------------------------------------------------------------------------------------------------------------------
// Initial setup

// Global variable used to disable controls after clicking
const GLOBAL = {"controls_enabled": true};

// Run scan on start-up
run_scan()


// ---------------------------------------------------------------------------------------------------------------------
// Define functions

// .....................................................................................................................

async function run_scan() {

  // Prevent multiple scans being queued up
  if (GLOBAL.controls_enabled){

    // Communicate scan-in-progress state to user
    show_msg("Scanning...");
    set_to_scan_in_progress();

    // Request port scan results (list of open ip addresses) from the server
    let rtsp_results_json = {};
    try {
        const flask_data_json_str = await fetch(build_rtsp_scan_url());
        rtsp_results_json = await flask_data_json_str.json();
        show_scan_results_msg(rtsp_results_json);

    } catch {
        console.log("Error! Couldn't fetch data from server, likely down?");
        show_msg(["Scan error!", "Server may be down..."]);
    }

    // Undo all 'in-progress' ui changes
    return_from_scan_in_progress();
    console.log("Scan results:", rtsp_results_json);
  }
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

function show_msg(message_strings) {

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

function show_scan_results_msg(rtsp_results_json) {

  /*
  // FOR DEBUG (generate example ips to display)
  rtsp_results_json = {}
  ips = []
  for(let i = 0; i < 24; i++){
    ips[i] = `192.168.0.${5 + i}`;
  }
  rtsp_results_json = {"open_ips_list": ips}
  */

  // Clear existing scan results
  const scan_results_div = clear_scan_results();

  // Unpack the result (with defaults assuming this fails)
  const {open_ips_list = [], base_ip_address = null, port = 554} = rtsp_results_json;

  // Bail if we don't get any IP addresses open
  const no_open_ips = (open_ips_list.length == 0);
  if(no_open_ips) {
    const missing_base_ip = (base_ip_address === null);
    const no_base_ip_msg = "Couldn't determine IP range to scan!";
    const no_open_ips_msg = ["No IP addresses with open RTSP ports!", `Searched: ${base_ip_address}`];
    const feedback_msg = missing_base_ip ? no_base_ip_msg : no_open_ips_msg;
    show_msg(feedback_msg);
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

}

// .....................................................................................................................

function clear_scan_results() {

  /* Helper function used to clear existing scan results */

  // Get a reference to the scan results div and remove everything inside
  const scan_results_div = getelem_scan_results();
  while(scan_results_div.firstChild){
    scan_results_div.removeChild(scan_results_div.firstChild);
  }

  return scan_results_div
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
