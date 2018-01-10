/*
 * Ensures that tabs cannot escape the user's selection to the address bar, and
 * that they can only occur between elements that have tabindices
 */
function suppress(key, up, down, press) { 
    up = up == undefined ? true : up
    down = down == undefined ? true : down
    press = press == undefined ? true : press

    var disabler = function(e) { if (e.which == key) { e.preventDefault();}};
    if (up) { $(document).on("keyup", disabler); };
    if (down) { $(document).on("keydown", disabler) } ;
    if (press) { $(document).on("keypress", disabler)} ;
}

$(document).on("keyup", tabKeyUp);
function tabKeyUp(e) {
    if (e.which == 9) {
        console.log("Tab key caught!");
        e.preventDefault();
        tabToNext();
    }
}
function tabToNext() {
    var focused = $(document.activeElement);
    var focusedTi = focused.attr("tabindex") || 0;
    console.log(focusedTi);
    var target = $('[tabindex='+ (focusedTi + 1) +']')[0];
    console.log(target);
    if (!target) {
        target = $('[tabindex=1]')[0];
    }
    target.focus();
}

suppress(9); // suppress tab
