
// --------------------------------------------------------------------------------------------------------------------
// Flask provides variables for selections
// selections_global = {"camera_select": ..., "user_select": ..., "task_select": ..., "rule_select": ..., "video_select": ...}}
// project_tree_global = dictionary storing all camera/user/task/rule/video info (console log it to check the structure)
// redirected_global = boolean indicating whether the user was redirected to this page (eg. due to missing selections)
// --------------------------------------------------------------------------------------------------------------------


// --------------------------------------------------------------------------------------------------------------------
// Dropdown button functions
// --------------------------------------------------------------------------------------------------------------------

function hide_dropdown_menus(){
    Object.values(ul_id_lut_global).forEach(ul_id => {
        document.getElementById(ul_id).style.display = "none";
    });
}

// ....................................................................................................................

function show_dropdown_menu(select_type){

    function dropdown_callback() {

        // Get the initial state, since we'll use that to toggle the display state
        const ul_ref = document.getElementById(ul_id_lut_global[select_type]);
        const initially_hidden = (ul_ref.style.display == "none");

        // First hide all dropdowns
        hide_dropdown_menus();

        // Toggle the display state of the selected dropdown
        if (initially_hidden) {
            ul_ref.style.display = "block";
        }

        /*
        // For debugging
        console.log("Show dropdown:", select_type);
        console.log("      Menu ID:", ul_id);
        */
    }
    return dropdown_callback;
}

// ....................................................................................................................

function attach_dropdown_callbacks(){
    Object.entries(btn_id_lut_global).forEach(([select_type, btn_id]) => {
        document.getElementById(btn_id).addEventListener("click", show_dropdown_menu(select_type));
    });
}

// ....................................................................................................................



// --------------------------------------------------------------------------------------------------------------------
// Menu HTML builder functions
// --------------------------------------------------------------------------------------------------------------------

function _build_menu(select_type, build_list) {

    // Update the dropdown button text for the given select_type
    const btn_id = btn_id_lut_global[select_type];
    const btn_ref = document.getElementById(btn_id);
    const selected_text = selections_global[select_type];
    btn_ref.innerText = (selected_text == null) ? "--- No Selection ---" : selected_text;

    // Clear the dropdown menu entries for the given select_type
    const ul_id = ul_id_lut_global[select_type];
    const ul_ref = document.getElementById(ul_id);
    while(ul_ref.firstChild) { 
        ul_ref.firstChild.remove(); 
    }

    /*
    // For debugging
    console.log("REBUILDING", select_type);
    console.log("  Selection:", selected_text);
    console.log("  Menu list:", build_list)
    */

    // Add a list entry for each possible selection in the menu and add it to the HTML
    build_list.forEach(list_entry => {
        const new_li = document.createElement("li");
        new_li.innerHTML = list_entry;
        new_li.addEventListener("click", dropdown_menu_item_callback(select_type));
        ul_ref.appendChild(new_li);
    });
}

// ....................................................................................................................

// Menu builder functions
var build_camera_menu = (camera_list) => _build_menu("camera_select", camera_list);
var build_user_menu = (user_list) => _build_menu("user_select", user_list);
var build_task_menu = (task_list) => _build_menu("task_select", task_list);
var build_video_menu = (video_list) => _build_menu("video_select", video_list);

// ....................................................................................................................

function update_menus(){

    // Get the selections needed to fill out the menus
    const camera_select = selections_global["camera_select"];
    const user_select = selections_global["user_select"];

    // Get the camera list
    let camera_list = Object.keys(project_tree_global);
    let video_list = []; 
    let user_list = [];
    let task_list = [];

    // Try to get the video list, or return an empty list
    try { video_list = project_tree_global[camera_select]["videos"]["names"]; }
    catch {}

    // Try to get the user list, or return an empty list
    try { user_list = Object.keys(project_tree_global[camera_select]["users"]); } 
    catch {}

    // Try to get the task list, or return an empty list
    try { task_list = Object.keys(project_tree_global[camera_select]["users"][user_select]["tasks"]); }
    catch {}

    // Finally, build all the menu HTML using the appropriate lists
    build_camera_menu(camera_list);   
    build_video_menu(video_list);
    build_user_menu(user_list);
    build_task_menu(task_list);
}

// ....................................................................................................................



// --------------------------------------------------------------------------------------------------------------------
// Selection updating functions
// --------------------------------------------------------------------------------------------------------------------

function post_selections_to_server(debug_feedback = false){
    const selections_update_url = "/update_selections";
    const fetch_param = {
                            headers: {"content-type": "application/json"},
                            method: 'post',
                            body: JSON.stringify(selections_global)
                        }

    fetch(selections_update_url, fetch_param)
    .then(response => { 
        if(debug_feedback) console.log("POST RESPONSE:", response);
    });
}

// ....................................................................................................................

function clear_selection_chain(select_type) {

    // Clear dependent selections when a selection is altered
    //      For example, if the camera selection is changed, the video/user/task/rule selections ...
    //      ... generally don't carry over to a different camera, so they should be cleared!
    switch(select_type) {

        case "camera_select":
        selections_global["user_select"] = null;
        selections_global["task_select"] = null;
        selections_global["video_select"] = null;
        selections_global["rule_select"] = null;
        break;

        case "user_select":
        selections_global["task_select"] = null;
        selections_global["rule_select"] = null;
        break;

        case "task_select":
        selections_global["rule_select"] = null;
        break;

        case "rule_select":
        // Do nothing
        break

        case "video_select":
        // Do nothing
        break

        default:
        console.log("ERROR: Unrecognized selection -", select_type);
        break;

    }
}

// ....................................................................................................................

function update_selections_record(select_type, new_selection) {

    // First check if the new selection is different from it's previous value
    const old_selection = selections_global[select_type];
    const selection_changed = (old_selection != new_selection)

    // Update the selection
    selections_global[select_type] = new_selection

    return selection_changed
}

// ....................................................................................................................

function dropdown_menu_item_callback(select_type){

    function custom_callback(){

        // Try updating the selection
        const new_selection = this.innerText;
        selection_changed = update_selections_record(select_type, new_selection)

        // Only rebuild the menus if we got a new selection
        if (selection_changed) {

            // Update all of the menu HTML graphics
            clear_selection_chain(select_type);
            update_menus();

            // Tell the server about the new selections
            post_selections_to_server();
        }

        // Hiden the dropdown menus after the user selects an entry
        hide_dropdown_menus();
    }
    return custom_callback;
}

// ....................................................................................................................

function incomplete_selection_alert(){

    // Figure out if any selections are null (not including 'rule_select', if present)
    const relevant_selections = Object.entries(selections_global).filter(([key, val]) => key != "rule_select");
    const has_null_selections = relevant_selections.flat().includes(null);

    // If we got redirected to this page, alert if not all selections have been made
    if(redirected_global && has_null_selections) {
        window.alert("Must complete selections before configuration!");
    }
}

// ....................................................................................................................



// --------------------------------------------------------------------------------------------------------------------
// Initial setup
// --------------------------------------------------------------------------------------------------------------------

// ID lookups for convenience
const btn_id_lut_global = {
    "camera_select": "camera_selection_btn",
    "user_select": "user_selection_btn",
    "task_select": "task_selection_btn",
    "video_select": "video_selection_btn"
};
const ul_id_lut_global = {
    "camera_select": "camera_selection_menu_list",
    "user_select": "user_selection_menu_list",
    "task_select": "task_selection_menu_list",
    "video_select": "video_selection_menu_list"
};

// Create all the (initial) menu HTML based on the initial selections
hide_dropdown_menus();
update_menus();
attach_dropdown_callbacks();
incomplete_selection_alert();

// --------------------------------------------------------------------------------------------------------------------
// --------------------------------------------------------------------------------------------------------------------

