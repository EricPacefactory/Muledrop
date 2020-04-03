
// ---------------------------------------------------------------------------------------------------------------------
// Define html/css/url helper functions

// DOM access helpers
const getelem_camera_title = () => document.getElementById("camera_title_div");
const getelem_display = () => document.getElementById("display_image_elem");
const getelem_objindex_indicator = () => document.getElementById("objindex_indicator_span");
const getelem_objid_tooltip = () => document.getElementById("objid_tooltip_span");
const getelem_left_arrow = () => document.getElementById("left_arrow_button_div");
const getelem_right_arrow = () => document.getElementById("right_arrow_button_div");
const getelem_label_block = () => document.getElementById("label_block_ul");
const getelem_label_buttons_array = () => Array.from(getelem_label_block().querySelectorAll("li"));

// Label button css-class control functions
const css_highlight_label_button = (label_button_ref) => label_button_ref.className = "label_button_hl_li";
const css_normal_label_button = (label_button_ref) => label_button_ref.className = "label_button_li";

// Image/animation display helper functions
const get_display_src = () => getelem_display().src;
const set_display_src = (display_src) => getelem_display().src = display_src;

// Route-URL builders
const build_setup_request_url = () => `/setuprequest`;
const build_label_update_url = () => `/labelupdate`;
const build_label_request_url = (object_id) => `/labelrequest/${object_id}`;
const build_display_image_url = (object_id) => `/imagerequest/${object_id}`;
const build_display_animation_url = (object_id) => `/animationrequest/${object_id}`;


// ---------------------------------------------------------------------------------------------------------------------
// Initial setup
// (All 'manually' run code is here! Everything else is handled with callbacks)

// Define some globally used variables. These shouldn't be used directly! Use set/get functions instead!
//   (note: using 'let' instead of 'var' hides these from the console!)
let _global_consts = {"object_id_list": []};
let _global_state = {"current_object_index": 0, "label_buttons_enabled": false, "display_state": "image"};

// Make initial request for data needed to generate starting UI
fetch(build_setup_request_url())
.then(flask_data_json_str => flask_data_json_str.json())
.then(setup_global_constants_and_state)
.then(setup_initial_ui)
.then(update_ui_for_new_object)
.catch(error => console.error("Setup error:", error))


// ---------------------------------------------------------------------------------------------------------------------
// Define functions

// .....................................................................................................................

function setup_global_constants_and_state(setup_json_data) {

    // Some feedback
    console.log("Got setup data:", setup_json_data);

    // Store global constants.
    const object_id_list = setup_json_data["object_id_list"];
    _global_consts["object_id_list"] = object_id_list

    // Set initial state
    set_current_object_index(0);

    return setup_json_data
}

// .....................................................................................................................

function setup_initial_ui(setup_json_data){

    // Pull out only the terms we need to setup the constant UI elements
    const {camera_select, user_select, ordered_labels_list, ...rest} = setup_json_data;

    // Set up camera title & dynamically create class label buttons
    create_camera_title(camera_select, user_select);
    create_label_buttons(ordered_labels_list);

    // Attach image/animation toggle callback to the image element
    const image_elem = getelem_display();
    image_elem.addEventListener("click", toggle_display_callback);

    // Attach prev/next callbacks to arrow buttons
    const left_arrow_div = getelem_left_arrow();
    const right_arrow_div = getelem_right_arrow();
    left_arrow_div.addEventListener("click", cycle_objects_callback(-1));
    right_arrow_div.addEventListener("click", cycle_objects_callback(+1));
}

// .....................................................................................................................

function update_ui_for_new_object(){

    // Helper function which handles all updates needed when switching to a new object
    set_object_id_title();
    set_pixel_display_state("image");
    update_label_button_highlighting();
}

// .....................................................................................................................

function set_object_id_title(){

    // Get current selected object index & total number of objects, for feedback
    const show_object_index = 1 + get_current_object_index();
    const num_objects = get_object_count();

    // Display the object index (i.e. count)
    const index_indicator = `Object: ${show_object_index} / ${num_objects}`;
    const object_index_indicator_div = getelem_objindex_indicator();
    object_index_indicator_div.innerText = index_indicator;
}

// .....................................................................................................................

function update_label_button_highlighting(){

    // Get the current object id so we can request it's current labelling data
    const current_object_id = get_current_object_id();

    // Make the request for the object labelling data, then highlight the correspond class label button
    const label_request_url = build_label_request_url(current_object_id)
    fetch(label_request_url)
    .then(flask_data_json_str => flask_data_json_str.json())
    .then(label_request_json_data => label_request_json_data["class_label"])
    .then(update_label_button_styling)
    .catch(error => console.error("Label button update error:", error))
}

// .....................................................................................................................

function cycle_objects_callback(add_to_index){

    // Function used to increment/decrement (based on functon arg value) the current object index
    function inner_cycle_objects_callback(){

        // Get the current object index (which we'll soon change) & total object count, for handling wrap-around
        const current_object_index = get_current_object_index();
        const num_objects = get_object_count();

        // Handle both incrementing & decrementing wrap around
        let new_object_index = (current_object_index + add_to_index) % num_objects;
        if (new_object_index < 0){
            new_object_index = num_objects + add_to_index;
        }

        // Update the currently selected object index & update the UI correspondingly
        set_current_object_index(new_object_index);
        update_ui_for_new_object();
    }

    return inner_cycle_objects_callback
}

// .....................................................................................................................

function toggle_display_callback(){

    // Get the current display state so we know which one to switch to
    const current_display_state = get_pixel_display_state();

    // Toggle between image/animation, depending on the whatever the current state is
    let new_display_state = current_display_state;
    switch(current_display_state){
        case "image":
            new_display_state = "animation";
            break;
        case "animation":
            new_display_state = "image";
            break;
        default:
            console.log("ERROR - Couldn't toggle display state. Unrecognized state:", current_display_state)
    }

    // Force display update
    set_pixel_display_state(new_display_state);
}

// .....................................................................................................................

function update_pixel_display_visuals(){

    // Get the current state so we set the display properly
    const current_display_state = get_pixel_display_state();
    const current_object_id = get_current_object_id();

    // Update visuals based on the current display state & selected object
    switch(current_display_state){
        case "image":
            const image_url = build_display_image_url(current_object_id);
            set_display_src(image_url)
            break;
        case "animation":
            const animation_url = build_display_animation_url(current_object_id);
            set_display_src(animation_url)
            break;
        default:
            console.log("ERROR - Couldn't set display! Unrecognized display state:", current_display_state);
    }
}

// .....................................................................................................................

function create_camera_title(camera_select, user_select){

    // Create the camera/user title text at the top of the UI. This won't change after initial setup
    const camera_title_div = getelem_camera_title();
    const nice_camera_select = camera_select.replace("_", " ");
    camera_title_div.innerText = `${nice_camera_select} (${user_select} user)`;
}

// .....................................................................................................................

function create_label_buttons(ordered_labels_list){

    // Create each of the class label buttons at the bottom of the UI. These won't change after initial setup
    const label_block_ul = getelem_label_block();
    for(const each_label_string of ordered_labels_list){

        // Create label buttons with attribute we can use to check label string (instead of relying on innerText)
        const new_label_button = document.createElement("li");
        new_label_button.innerText = each_label_string;
        new_label_button.setAttribute("class_label_string", each_label_string);

        // Attach label update callback to each button
        new_label_button.addEventListener("click", update_object_label_callback(each_label_string));

        // Finally, add the new button (li) to the parent ul-element
        label_block_ul.appendChild(new_label_button);
    };

    // Lastly, make sure these buttons work after creation!
    enable_label_buttons();
}

// .....................................................................................................................

function update_object_label_callback(new_class_label){

    // Some settings shared by all label buttons
    const fetch_method = "POST";
    const fetch_headers = {"Content-Type": "application/json"};

    // Function which tells the server to update/save a new class label for the currently selected object
    function inner_update_object_label_callback(){

        // Don't do anything if the button are disabled (only occurs temporarily, after another button was pressed)
        const label_buttons_are_enabled = get_label_button_enable_state();
        if(!label_buttons_are_enabled){
            return;
        }

        // Get current object id & construct label update data
        const current_object_id = get_current_object_id();
        const label_update_data = {object_id: current_object_id, 
                                   new_class_label_string: new_class_label};

        // Some debugging feedback
        console.log(`label update -> ${current_object_id} : ${new_class_label}`);
        
        // Build full POST data
        const post_data_json = {method: fetch_method, 
                                headers: fetch_headers, 
                                body: JSON.stringify(label_update_data)}

        // Post data to server for update, delay for label update feedback, then cycle to the next object
        const label_update_url = build_label_update_url();
        fetch(label_update_url, post_data_json)
        .then(disable_label_buttons)
        .then(update_label_button_highlighting)
        .then(delay_promise_ms(350))
        .then(cycle_objects_callback(+1))
        .then(enable_label_buttons)
        .catch(error => console.error("Label update error:", error))
    }

    return inner_update_object_label_callback
}

// .....................................................................................................................

function update_label_button_styling(current_object_class_label){

    // Check the class label on each button and highlight the one matching the current object label
    let label_button_array = getelem_label_buttons_array();
    for(const each_label_button_ref of label_button_array){
        const button_class_label_string = each_label_button_ref.getAttribute("class_label_string");
        if(button_class_label_string == current_object_class_label){
            css_highlight_label_button(each_label_button_ref);
        } else {
            css_normal_label_button(each_label_button_ref);
        }
    }
}

// .....................................................................................................................

function delay_promise_ms(delay_ms){

    // Helper function which can be used to insert a delay into .then(...) chains
    // (from https://stackoverflow.com/questions/38956121/how-to-add-delay-to-promise-inside-then)
    return function(input_value_before_delay) {
        return new Promise(resolve => setTimeout(() => resolve(input_value_before_delay), delay_ms));
    };
}

// .....................................................................................................................
// .....................................................................................................................



// ---------------------------------------------------------------------------------------------------------------------
// Define global state access functions

// .....................................................................................................................

function set_current_object_index(object_index){
    _global_state["current_object_index"] = object_index;
}

// .....................................................................................................................

function get_current_object_index(){
    return _global_state["current_object_index"];
}

// .....................................................................................................................

function enable_label_buttons(){
    _global_state["label_buttons_enabled"] = true;
}

// .....................................................................................................................

function disable_label_buttons(){
    _global_state["label_buttons_enabled"] = false;
}

// .....................................................................................................................

function get_label_button_enable_state(){
    return _global_state["label_buttons_enabled"];
}

// .....................................................................................................................

function set_pixel_display_state(new_display_state){

    // Update global record of the display state
    _global_state["display_state"] = new_display_state;

    // Make sure the UI visuals match the new internal display state
    update_pixel_display_visuals();
}

// .....................................................................................................................

function get_pixel_display_state(){
    return _global_state["display_state"];
}

// .....................................................................................................................
// .....................................................................................................................



// ---------------------------------------------------------------------------------------------------------------------
// Define global constants access functions

// .....................................................................................................................

function get_current_object_id(){
    const current_object_index = get_current_object_index();
    return _global_consts["object_id_list"][current_object_index];
}

// .....................................................................................................................

function get_object_count(){
    return _global_consts["object_id_list"].length;
}

// .....................................................................................................................
// .....................................................................................................................



// ---------------------------------------------------------------------------------------------------------------------
// Scrap

// TODOs
// - better visual feedback for cycling between objects (slide image left/right maybe?)

