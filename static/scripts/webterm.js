function invertRect(context, x, y, w, h) {
    // Source: http://stackoverflow.com/questions/i6985098/html5-inverse-text-color-on-canvas
    var ddata = context.getImageData(x, y, w, h);
    var dd = ddata.data;
    var len = dd.length;
    for (var i = 0; i < len; i += 4) {
        dd[i] = 255 - dd[i];
        dd[i + 1] = 255 - dd[i + 1];
        dd[i + 2] = 255 - dd[i + 2];
    }
    context.putImageData(ddata, x, y);
}

api = {
    socket: null,
    lastId: 0,
    pending: {},
    handlers: {},
    messages: { 
        screen      : "%",
        changes     : "?",
        settings    : "s",
        hello       : "h",
        keypress    : "k",
        cursor      : "_",
        error       : "e",
        chat        : ":",
        leave       : "l",
        status      : "u",
        owner       : "~"
    },
    colorsByName: {
        black   : 0,
        red     : 1,
        green   : 2,
        brown   : 3,
        blue    : 4,
        magenta : 5,
        cyan    : 6,
        white   : 7
    },
    colorsByNumber: [
        "black", "red", "green", "brown", "blue", "magenta", "cyan", "white"
    ],
    connect: function() {
        this.socket = io.connect('/api');
        this.socket.on("message", this.handleMessage);
        return this.socket
    },
    handleMessage: function(data) {
        var passedObject = $.parseJSON(data);
        for (i in api.pending) {
            if (i == passedObject.id) {
                api.pending[i].resolveWith(api, passedObject.response.slice(1));
                    // cut off type indicator.
                delete api.pending[i];
                break;
            }
        }
        var type = passedObject.response[0];
        if (type in api.handlers) {
            for (var i = 0; i < api.handlers[type].length; i++) {
                api.handlers[type][i].apply(api, passedObject.response.slice(1));
            }
        }
    },  
    on: function(type, handler) {
        if (type in api.handlers) {
            api.handlers[type].push(handler);
        } else {
            api.handlers[type] = [handler];
        }
    },
    request: function(msg, args) {
        // Low-level request function.
        // Takes a list which comprises the request body.
        if (this.socket === null) { throw "not connected"; }

        var id = this.lastId;
        this.socket.send(JSON.stringify({
            id      : id,
            request : [msg].concat(args)
        }));
        var def = $.Deferred();
        this.pending[id] = def;
        this.lastId++;
        return def;
    },
    requestSettings: function() {
        return api.request(api.messages.settings, []);
    },
    requestChanges: function(lastChange) {
        return api.request(api.messages.changes, [lastChange]);
    },
    requestScreen: function() {
        return api.request(api.messages.screen, []);
    },
    requestHello: function() {
        return api.request(api.messages.hello, ['hello']);
    },
    requestKeypress: function(k) {
        return api.request(api.messages.keypress, [k]);
    },
    requestChat: function(message) {
        return api.request(api.messages.chat, [message]);
    },
    requestLeave: function() {
        return api.request(api.messages.leave, []);
    },
    requestOwner: function() {
        return api.request(api.messages.owner, []);
    }
}

function expandChar(c) {
    if ((typeof c) == 'string') {
        return [c, 56];
        // it's using an implicit 56
    } else {
        return c; // it's normal
    }
}

function expandRow(row) {
    newRow = [];
    for (var i = 0; i < row.length; i++) {
        if ((typeof row[i]) == 'number') {
            // int
            for (var j = 0; j < row[i]; j++) {
                newRow.push(newRow[newRow.length - 1]);
            }
        } else {
            newRow.push(expandChar(row[i]));
        }
    }
    return newRow;
}   


function createConsole(owner, rows, cols) {
    var defaultChar = [" ", 56];

    var cW = 8; // width of a character
    var cH = 14; // height of one
    var cB = 4; // how much a character can go below the bottom line
    var font = "12pt FixedsysExcelsior301Regular";

    var cnsColorScheme = colorScheme; // load global color scheme

    var cnvSpan = document.createElement("span");
    cnvSpan.className = "consoleBorder";

    var cnv = document.createElement("canvas");

    var cnsOwner = 0;

    cnv.width = cW * cols;
    cnv.height = cH * rows;
    cnv.className = "console";

    var cnsGrid = [];
    var cursor = [-1, -1];
    for (var y = 0; y < rows; y++) {
        var row = [];
        for (var x = 0; x < cols; x++) {
          row.push(defaultChar);
        }
        cnsGrid.push(row);
    } 

    function replaceRow (rowY, newRow) {
        cnsGrid[rowY] = newRow;
        redrawRow(rowY);
    }

    function resolveColors(scheme, pair) {
        var bgIdx = pair % 8;
        var fgIdx = (pair >> 3) % 8;
        var isBold          = (pair & (1 << 6 )) != 0;
        var isItalic        = (pair & (1 << 7 )) != 0;
        var isUnderscored   = (pair & (1 << 8 )) != 0;
        var isStruckThrough = (pair & (1 << 9 )) != 0;
        var isReversed      = (pair & (1 << 10)) != 0;
        var isBrightFg = isBold;
        var isBrightBg = isItalic || isUnderscored || isStruckThrough;
            // I don't know which of these represents BLINK
        var bg, fg;
        if (isBrightFg) {
            fg = scheme.bright[fgIdx];
        } else {
            fg = scheme.dark[fgIdx];
        }

        if (isBrightBg) {
            bg = scheme.bright[bgIdx];
        } else {
            bg = scheme.dark[bgIdx];
        }
       
        if (isReversed) {
            return [fg, bg];
        } else {
            return [bg, fg];
        }
    }

    function redrawChar(cX, cY) {
        var xPos = cW * cX;
        var yPos = cH * cY;

        var g = cnsGrid;
        var charPair_ = g[cY];
        var charPair = charPair_[cX];

        var character = charPair[0];
        var colors = resolveColors(cnsColorScheme, charPair[1]);

        var bg = colors[0];
        var fg = colors[1];

        var ctx = cnv.getContext('2d');

        ctx.fillStyle = bg;

        ctx.fillRect(xPos, yPos, Math.floor(cW), Math.floor(cH));

        ctx.fillStyle = fg;
        ctx.font = font;
        ctx.fillText(character, xPos, yPos + cH - cB, cW);

        if (cX == cursor[0] && cY == cursor[1]) {
            // draw the cursor
            invertRect(ctx, xPos, yPos + cH - cB, cW, cB)
        } 
       
    }

    function redrawRow(rowY) {
        for (var cX = 0; cX < cols; cX++) {
            redrawChar(cX, rowY);
        }
    }

    function redraw() {
        var ctx = cnv.getContext('2d');
        ctx.fillStyle = "#000000";
        ctx.fillRect(0, 0, cnv.width, cnv.height);

        for (var cY = 0; cY < rows; cY++) {
            redrawRow(cY);
        }
    }

    function moveCursor(x, y) {
        oldRow = cursor[1];
        cursor = [x, y]; // 1-indexed
        newRow = cursor[1];
        if (oldRow == newRow) {
            redrawRow(oldRow);
        } else {
            if (oldRow != -1) {redrawRow(oldRow);}
            redrawRow(newRow);
        }
    }

    function setColorScheme(newscheme) {
        cnsColorScheme = newscheme;
        redraw();
    }
    var cc = function(character) { return character.charCodeAt(0); }
    var kc = function(key) { return String.fromCharCode(key); } 

    var ESC = kc(0x1b);

    var keyManager = {
        isModified: function (key) {
            return key.shiftKey || key.ctrlKey || key.altKey || key.metaKey;
        },
        controlKey: function (ch) {
            // ch is the string representation of the key
            return ch.charCodeAt(0) - "A".charCodeAt(0) + 1;
        },
        keyDown: function (e) {
            if ((e.keyCode || e.which) == 13) { keyManager.send([13]); return; }
            if (e.keyCode in keyManager.specialCases) {
                var basic = keyManager.specialCases[e.keyCode];
                var out = [];
                for (var i = 0; i < basic.length; i++) {
                    for (var j = 0; j < basic[i].length; j++) {
                        out.push(cc(basic[i][j]));
                    }
                }
                keyManager.send(out);
                return false;
            } else if (keyManager.getChar(e) && keyManager.getChar(e) >= 'A') {
                if (e.ctrlKey) {
                    keyManager.send([keyManager.controlKey(keyManager.getChar(e))])
                    return false;
                    }
            }
        },
        specialCases: {
            8  : [kc(0x7f)], // backspace
    
            27 : [ESC], // escape
    
            112: [ESC, 'OP'], // F keys
            113: [ESC, 'OQ'],
            114: [ESC, 'OR'],
            115: [ESC, 'OS'],
            116: [ESC, '[15~'],
            117: [ESC, '[17~'],
            118: [ESC, '[18~'],
            119: [ESC, '[19~'],
            120: [ESC, '[20~'],
            121: [ESC, '[21~'],
            122: [ESC, '[23~'],
            123: [ESC, '[24~'],
            
            33:  [ESC, '[5~'], // pageup
            34:  [ESC, '[6~'], // pagedown
            // 35:  [ESC, '4~'], // end
            // 36:  [ESC, '1~'], // home
            37:  [ESC, 'OD'], // left
            38:  [ESC, 'OA'], // up
            39:  [ESC, 'OC'], // right
            40:  [ESC, 'OB']  // down
    
        },
        keyUp: function (e) {
        },
        keyPress: function (e) {
            keyManager.send([keyManager.getChar(e).charCodeAt(0)]);
            return false;
        },
        getChar: function (event) {
            if (event.which == null) {
                return String.fromCharCode(event.keyCode);
            } else if (event.which != 0 && event.charCode != 0) {
                return String.fromCharCode(event.which);
            } else {
                return null;
            }
        },
        send: api.requestKeypress
    };

    var changeOwner = function (newOwner) {
        cnsOwner = newOwner; // TODO: Somehow graphically represent this
        $(cnv).css("border-color", colorScheme.ownership[newOwner]);
        console.log("New owner: " + newOwner);
    }

    $(cnv).attr("tabindex", 2);
    $(cnv).bind("keydown", keyManager.keyDown);
    $(cnv).bind("keyup", keyManager.keyUp);
    $(cnv).bind("keypress", keyManager.keyPress);

    cnvSpan.appendChild(cnv);
    owner.appendChild(cnvSpan);

    redraw();

    return {
        replaceRow: replaceRow,
        moveCursor: moveCursor,
        setColorScheme: setColorScheme,
        changeOwner: changeOwner
    };
}

function createChatPane(region) {
    var pane = document.createElement('div');

    var inputBox = document.createElement('input');
    inputBox.className = 'chatInput';
    $(inputBox).attr("tabindex", 1);
    $(inputBox).attr("id", "chatInput"); 

    var inputSpan = document.createElement('span');
    inputSpan.className = 'chatInputSpan';
    inputSpan.appendChild(inputBox);

    var label = document.createElement('label');
    label.className = "chatLabel";
    label.htmlFor = "chatInput";
    label.appendChild(document.createTextNode(":: "));

    var chatBox = document.createElement('table');
    chatBox.className = 'chatOutput';

    var chatDiv = document.createElement('div');
    chatDiv.appendChild(chatBox);
    chatDiv.className = 'chatDiv';

    var chatInputDiv = document.createElement('div');
    chatInputDiv.className = 'chatInputDiv';
    chatInputDiv.appendChild(label);
    chatInputDiv.appendChild(inputSpan);

    pane.appendChild(chatDiv);
    pane.appendChild(chatInputDiv);
    region.appendChild(pane);
    var hitEnter = function (e) {
        if (e.which == 13) {
            sendLine(inputBox.value);
            inputBox.value = "";
        }
    }

    $(inputBox).on("keydown", hitEnter)

    var addLabeledLine = function(sender, line) {
        var leeway = 40;
            // 40 pixels from bottom is close enough to count
        var scrolledDown = chatDiv.scrollTop >= chatDiv.scrollHeight - $(chatDiv).height() - leeway;
        // var scrolledDown = true;

        var chatRow = chatBox.insertRow(-1);
        var senderName = chatRow.insertCell(-1);
        senderName.className = "senderCell";
        var message = chatRow.insertCell(-1);
        message.className = "messageCell";
        senderName.appendChild(document.createTextNode(sender));
        message.appendChild(document.createTextNode(line));

        if (scrolledDown) { chatDiv.scrollTop = chatDiv.scrollHeight + $(chatRow).height(); }
            // If they were scrolled down before, continue scrolling down.
    }

    var addChat = function (sender, line) {
        addLabeledLine(sender + " :", line);
    }

    var addStatus = function(line) {
        addLabeledLine("*", line);
    }

    var addError = function(line) {
        addLabeledLine("!", line);
    }

    var sendLine = function(line) {
        api.requestChat(line);
    }

    var resizeTo = function (width, height) {
        console.log("Resizing for w=" + width +" and h= " + height);
        $(pane).css("height", height);
        var targetHeight = $(pane).innerHeight() - $(inputBox).height();
        $(chatDiv).css("height", targetHeight)
    }
    return {
        resizeTo    : resizeTo,
        addChat     : addChat,
        addStatus   : addStatus,
        addError    : addError
    }
}

var first = true;

sock = api.connect();
sock.on("connect", function () {
    api.requestSettings().done(
        function (settings) {
            if (!first) { return; }
            first = false;
            var rows = settings.rows;
            var cols = settings.cols;
            /* 
             * Create widgets.
             */
            var cns = createConsole($("#consoleRegion")[0], rows, cols);
            var chat = createChatPane($("#chatPaneRegion")[0])
            /* 
             * API events
             */

            api.on("%", function(screen) {
                for (var i = 0; i < screen.length; i++) {
                    var row = screen[i];
                    cns.replaceRow(i, expandRow(row));
                }
            });
            api.on("?", function(changes) {
                for (var i = 0; i < changes.length; i++) {
                    var change = changes[i];
                    var changeNumber = change[0]
                    var lineNumber = change[1];
                    var line = change[2];
                    cns.replaceRow(lineNumber, expandRow(line));
                }
            });
            
            api.on("_", cns.moveCursor);

            api.on(api.messages.owner, cns.changeOwner);

            api.on(api.messages.chat, chat.addChat);
            api.on(api.messages.status, chat.addStatus);
            api.on(api.messages.error, chat.addError);

            $(window).on("close", api.requestLeave);
            /*
             * Handle layout.
             */

            var fixLayout = function () {
                var width = window.innerWidth;
                var height = window.innerHeight;
                var fudge = 40; // Unaccounted-for space due to margins and padding.

                var remainingSpace = height - $("#consoleRegion").height();
                remainingSpace -= fudge;
                chat.resizeTo(width, remainingSpace); 
            }
            $(window).on("resize", fixLayout);
            fixLayout();

            /*
             * OK, start!
             */

            api.requestHello();
            api.requestScreen();
            api.requestOwner();
        }
    );
});



