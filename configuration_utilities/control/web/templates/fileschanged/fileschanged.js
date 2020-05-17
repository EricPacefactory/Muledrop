
// ---------------------------------------------------------------------------------------------------------------------
// Define html/css/url helper functions

// DOM access helpers
const getelem_main_container = () => document.getElementById("main_container");


// ---------------------------------------------------------------------------------------------------------------------
// Initial setup

create_all_camera_uis();


// ---------------------------------------------------------------------------------------------------------------------
// Define functions

// .....................................................................................................................

function create_all_camera_uis() {

    // Get reference to the container which we'll attach all camera entries to
    const container_ref = getelem_main_container();

    // Use the variable provided by flask to generate the UI
    // Data is stored as a dictionary (js object), 
    //   - where keys are cameras names
    //   - entries are lists of file paths that were changed
    const file_change_items = Object.entries(files_changed_json);
    for(const [each_camera_name, each_file_list] of file_change_items){
        const new_elem = create_one_camera_ui(each_camera_name, each_file_list)
        container_ref.appendChild(new_elem)
    }

    // If there aren't any entries, add a special indicator for better user feedback
    const no_change = (file_change_items.length == 0);
    if (no_change) {
        const no_change_elem = create_no_change_ui();
        container_ref.appendChild(no_change_elem);
    }
}

// .....................................................................................................................

function create_one_camera_ui(camera_name, file_list) {

    // Create parent container to hold all files listed for a single camera
    const new_camera_container = document.createElement("div");
    new_camera_container.className = "camera_container_div";

    // Create title block to show camera name & file count
    const new_camera_title_div = document.createElement("div");
    new_camera_title_div.className = "camera_title_div";

    // Create div to hold the camera name
    const new_camera_name_div = document.createElement("div");
    new_camera_name_div.className = "camera_name_div";
    new_camera_name_div.innerText = camera_name;

    // Create div to hold the file count
    const new_file_count_div = document.createElement("div");
    const file_count = file_list.length;
    new_file_count_div.className = "file_count_div";
    new_file_count_div.innerText = `(${file_count} files)`;

    // Create new list to hold file path entries
    const new_file_list_ul = document.createElement("ul");
    new_file_list_ul.className = "file_list_ul";

    // Add list entries for each of the changed file paths
    for(each_file_path of file_list){

        const new_file_li = document.createElement("li");
        new_file_li.className = "file_entry_li";
        new_file_li.innerText = each_file_path;

        new_file_list_ul.appendChild(new_file_li);
    }

    // Finally bundle all the nested elements together
    new_camera_title_div.appendChild(new_camera_name_div);
    new_camera_title_div.appendChild(new_file_count_div);
    new_camera_container.appendChild(new_camera_title_div);
    new_camera_container.appendChild(new_file_list_ul);

    return new_camera_container
}

// .....................................................................................................................

function create_no_change_ui() {

    // Create parent container to hold the 'no change' ui elements
    const new_warning_container = document.createElement("div");
    new_warning_container.className = "no_change_warning_div";

    // Create warning messages
    const new_text_row_1 = document.createElement("p");
    new_text_row_1.className = "no_change_p";
    new_text_row_1.innerText = "No files were changed!";

    // Add warning text to the warning container
    new_warning_container.appendChild(new_text_row_1);

    return new_warning_container
}

// .....................................................................................................................
// .....................................................................................................................


// ---------------------------------------------------------------------------------------------------------------------
// Scrap

// TODO
// - Show nesting/grouping of folders, would make the changes easier to read
//