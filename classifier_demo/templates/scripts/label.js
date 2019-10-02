
// *** FLASK VARIABLES
// Flask template provides two variables:
// task_id_lists:
//      dictionary -> Keys represent task names and corresponding values hold a sorted list of object ids
//
// ordered_label_list:
//      list -> each entry holds a tuple. 
//              The first element is an integer and represents the index used to represent the label (i.e. 0, 1, 2 etc.)
//              The second element is a string representing the label itself

// *** DATA ROUTES
// Multiple routes used for accessing object labels, object display images and animations.
//
// Object label requests -> /labelrequest/<string:task_name>/<int:object_id>
//      Used to ask for the current label associated with <object_id> from <task_name>
//      Returns a dictionary -> {"label_index": (int), "label_string": (string)}
//
// Object image requests -> /imagerequest/<string:task_name>/<int:object_id>
//      Used to ask for a representative image of <object_id> from <task_name>
//      Returns a base64 encoded jpg
//
// Object animation requests -> /animationrequest/<string:task_name>/<int:object_id>
//      Used to request a stream of jpgs representing an animation of <object_id> from <task_name>
//      Returns a sequence of base64 encoded jpgs

// --------------------------------------------------------------------------------------------------------------------
// Set up global variables used to keep track of what data we're working with
// --------------------------------------------------------------------------------------------------------------------

// Set up variables to store which task/object we're currently viewing (index into task_id_list)
var current_task_name = null;
var current_id_index = 0;
var animation_toggle = false;

// Figure out how many objects there are in total, for each task 
// Python reference: {each_task: len(each_id_list) for each_task, each_id_list in task_id_lists.items()}
var task_object_counts = {};
for (const [each_task, each_id_list] of Object.entries(task_id_lists)) {
    task_object_counts[each_task] = each_id_list.length;
}

/*
// Rube Goldberg code for counting the number of objects across all tasks (eg: sum(task_object_counts.values()))
reduce_sum_func = (accumulator, new_entry) => accumulator + new_entry;
const total_object_count = Object.values(task_object_counts).reduce(reduce_sum_func, 0);
*/


// --------------------------------------------------------------------------------------------------------------------
// Functions for requesting data
// --------------------------------------------------------------------------------------------------------------------

// ....................................................................................................................

function get_current_object_id(task_select = null, index_select = null){

    // Use global task/index selection if none are provided
    task_select = (task_select == null) ? current_task_name: task_select;
    index_select = (index_select == null) ? current_id_index: index_select;

    return task_id_lists[task_select][index_select];
}

// ....................................................................................................................

function update_label_state_indication(label_index){

    // Update label buttons to highlight the state associated with the response data
    // For example, if the response indicates label_index == 1, then
    // the 1-index button should be highlighted to indicate the object has that class label
    // (The buttons should already show the class labels from initial page load)

    // Reset all class label buttons to default class
    const default_class = "label_class_btn";
    const active_class = "active_label_class_btn";

    // Reset all li entries of class label ul html element
    const parent_ul = document.getElementById("label_class_buttons_ul");
    let li_nodes = parent_ul.children;
    for (each_li of li_nodes) {
        each_li.className = default_class;
    }
    
    // Highlight the class label button whose text matches the currently selected task name
    li_nodes = parent_ul.children;
    li_nodes[label_index].className = active_class;

}

// ....................................................................................................................

function update_image_display(task_name, object_id, debug_feedback = true) {

    /*
    Function for setting up the proper image/animation url for the display in the middle of the page
    */

    // Pick the appropriate url path (image or animation)
    const resource_route = animation_toggle ? "/animationrequest" : "/imagerequest";
    const request_url = [resource_route, task_name, object_id].join("/");

    // Handy feedback in console, if needed
    if (debug_feedback){
        console.log("NEWDISPLAY:", task_name, object_id);
        console.log("  url:", request_url);
    }

    // Set the image source url to get the proper image resource
    const img_div_id = "label_img_src";
    const img_div_ref = document.getElementById(img_div_id);
    img_div_ref.src = request_url;
}

// ....................................................................................................................

function label_request(task_name, object_id, debug_feedback = true){

    /*
    Function for requesting the label for a given object id
    */

    // Build the URL to request object label data
    const label_request_url = ["/labelrequest", task_name, object_id].join("/");

    if (debug_feedback){
        console.log("LABELREQUEST:", task_name, object_id);
        console.log("  url:", label_request_url);
    }

    fetch(label_request_url)
    .then(response => response.json())
    .then(response_data => {

        // Some feedback for debugging if needed
        if (debug_feedback){ console.log(response_data); }

        // Assume label request response is a dictionary with entries:
        // "label_index" -> Internal label mapping
        // "label_string" -> String associated with mapping
        // Update class label buttons
        const label_index = response_data["label_index"];
        update_label_state_indication(label_index);
    });

}

// ....................................................................................................................

function post_label_update_builder(label_index){

    /*
    Function for handling object label update (POST) requests. Used to change the classification label of the current object
    */

    function post_label_update(){

        const task_name = current_task_name;
        const object_id = get_current_object_id(task_name);
        const new_label_index = label_index;
        const debug_feedback = true;

        // Build the URL to post an object label update
        const label_update_url = "/labelupdate";

        // Build the json data to send for updating object label & bundle it for fetch function
        update_json = {"task_name": task_name, "object_id": object_id, "new_label_index": new_label_index}
        const fetch_param = {
            headers: {"content-type": "application/json"},
            method: 'post',
            body: JSON.stringify(update_json)
        }

        // For feedback
        if (debug_feedback){
            console.log("LABELUPDATE DATA:", update_json)

        }

        // Actual POST function
        fetch(label_update_url, fetch_param).then(response => {if(debug_feedback) console.log("LABELUPDATE RESPONSE:", response); });

        // If response is good, (indicate change in state?) and update to the next image/object
        update_label_state_indication(new_label_index);
        setTimeout(next_object, 350);
    }

    return post_label_update
}

// ....................................................................................................................

function update_index_display(object_id){

    /*
    Function for updating the "Viewing": x / total" text near the center/top of the page
    */

    const list_length_str = String(task_object_counts[current_task_name]);
    const num_display_digits = list_length_str.length;
    const nice_idx_str = String(1 + current_id_index).padStart(num_display_digits, "0");
    const display_str = `Viewing ${nice_idx_str} / ${list_length_str} (ID: ${object_id})`;
    document.getElementById("label_img_title").innerText = display_str;
}

// ....................................................................................................................

function update_task_display(){

    /*
    Function for updating the appearance of the upper task selection display, to 
    indicate which task is current selected/active
    */

    // Reset all task buttons to default class
    const default_class = "label_task_btn";
    const active_class = "active_label_task_btn";

    // Reset all li entries of task tab ul html element
    const parent_ul = document.getElementById("label_task_tabs_ul");
    let li_nodes = parent_ul.children;
    for (each_li of li_nodes) {
        each_li.className = default_class;
    }
    
    // Highlight the task button whose text matches the currently selected task name
    li_nodes = parent_ul.children;
    for (each_li of li_nodes) {
        if (each_li.innerText == current_task_name){
            each_li.className = active_class;
        }
    } 
}

// ....................................................................................................................

function update_task_select(){

    /*
    Function for changing the currently selected task. Also triggers updates to the 
    task selection indicator and the image that is displayed 
    */

    // Check if we're already on the selected task, in which case, do nothing
    const new_task_select = this.innerText;
    if (new_task_select == current_task_name) {
        console.log(`NO CHANGE! (${current_task_name})`);
        return
    }

    // If we don't bail above, then update the current task and reset the id index
    current_task_name = new_task_select;
    current_id_index = -1;
    next_object();

    // Update the css styling to show this button as being active/highlighted
    update_task_display();
}

// ....................................................................................................................

function next_object(){

    /*
    Function for switching to the next object for display/labelling
    */

    // Some debugging feedback
    console.log("NEXT OBJECT PLZ", "(at ", current_id_index, ")");

    // Update the current index being viewed, but make sure we don't go out-of-bounds on the id list
    let list_length = task_object_counts[current_task_name];
    current_id_index = (1 + current_id_index) % list_length;
    
    // Get the new object id base on the updated viewing index
    let new_object_id = get_current_object_id();

    // Request a new image & label data for the object
    reset_display_state();
    update_image_display(current_task_name, new_object_id);
    label_request(current_task_name, new_object_id, false);
    update_index_display(new_object_id);
}

// ....................................................................................................................

function prev_object(){

    /*
    Function for switching back to the previous object for display/labelling
    */

    // Some debugging feedback
    console.log("PREV OBJECT PLZ", current_id_index);

    // Update the current index being viewed, but make sure we don't go out-of-bounds on the id list
    let list_length = task_object_counts[current_task_name];
    current_id_index = current_id_index - 1;
    if (current_id_index < 0){
        current_id_index = list_length - 1;
    }
    
    // Get the new object id base on the updated viewing index
    let new_object_id = get_current_object_id();

    // Request a new image & label data for the object
    reset_display_state();
    update_image_display(current_task_name, new_object_id);
    label_request(current_task_name, new_object_id, false);
    update_index_display(new_object_id);
}

// ....................................................................................................................

function reset_display_state(){

    /*
    Function for reseting the display state, so that animation isn't constantly active
    */

    animation_toggle = false;
}

// ....................................................................................................................

function toggle_display_state(){

    /*
    Function for toggling whether the display shows an image or animation
    */

    // Swap the display state (image vs animation) & update the display accordingly!
    animation_toggle = !animation_toggle;
    let current_object_id = get_current_object_id();
    update_image_display(current_task_name, current_object_id);

    console.log("DISPLAYTOGGLE", "Animation:", animation_toggle);
}

// ....................................................................................................................

function initialize(){

    // Attach label updating functions to labelling buttons
    let label_buttons = document.getElementsByClassName("label_class_btn");
    for(let k = 0; k < label_buttons.length; k++){
        label_buttons.item(k).addEventListener("click", post_label_update_builder(k));
    }

    // Attach next/back functions to arrow buttons
    document.getElementById("prev_label_btn").addEventListener("click", prev_object);
    document.getElementById("next_label_btn").addEventListener("click", next_object);

    // Attach task selection function to task buttons
    let task_buttons = document.getElementsByClassName("label_task_btn");
    for(let k = 0; k < task_buttons.length; k++){
        task_buttons.item(k).addEventListener("click", update_task_select);
    }

    // Attach animation toggle to 'display' button
    document.getElementById("label_img_holder_div").addEventListener("click", toggle_display_state)

    // Set everything to a reasonable starting state
    current_task_name = Object.keys(task_id_lists)[0];
    current_id_index = -1;
    update_task_display();
    next_object();
}

// ....................................................................................................................
// ....................................................................................................................


// Launch everything without mucking up the global scope
initialize()
