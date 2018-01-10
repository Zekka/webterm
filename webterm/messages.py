import msgpack
from functools import wraps
import json

def pack(representation):
    return json.dumps(representation)

def unpack(representation):
    return json.loads(representation)

"""
Protocol (after unpacking):

---- Conventions ----

[[ x ]]
    list of x
[x, y]
    list containing [x, y]
x | y
    x or y
'text'
    string whose contents are 'text'
(x)
    optional x
{'key': x, 'key2': y}
    Map of {'key': x, 'key2', y}
&(x)
    packed (usually msgpack) x
    If this is used then the rest of the message is probably not msgpacked.
*x
    All defined representations matching .*x. (* is a wildcard)
%some meaningful phrase%
    An inline description as plain English of what something means within
    a representation.
{{ ? }}
    Some object of unknown form.

---- Vehicle ----

TODO: update for Socket.IO

---- Communications ----

hello_message: hello
    Server --> Client

hello_request: hello
    Server <-- Client

hello: ['h', 'hello']
    Server <-> Client
    Acknowledgement message sent at the beginning of a websocket connection.

change_request: ['?', change_number]
    Server <-- Client
    Represents a request by the client for all changes since the given change
    number.

    The server will respond either with a change_message containing all changes
    up to that point, or a screen_message containing the whole screen. The
    server will not include mutually-exclusive changes (changes made to the 
    same line). It should also send a screen_message if the change_number given
    is beyond its own current change_number.

    If the server does not remember enough changes or does not want to send as
    many changes as the client has requested, it can send a screen_message
    instead, which describes the entire screen.

screen_request: ['%']
    Server <-- Client
    Similar to a change_request, but does not specify a change number and
    always receives a screen_message in reply.

settings_request: ['s']
    Server <-- Client
    Requests information about the terminal from the server.

keypress_request: ['k', key]
    Server <-- Client
    Asks the server to press a key.
    Server should reply with an OkMessage.

leave_request: ['l']
    Server <-- Client
    Asks to leave.

    Server should reply with an OkMessage and then terminate the connection.

change_message: ['?', [[ change ]] ]
    Server --> Client
    Represents a change as transmitted to a client.

screen_message: ['%', [[ line ]], change_number ]
    Server --> Client
    Represents an entire screen. The list of lines represents the rows of the
    screen printed from top to bottom. The change_number is the number of the
    most recent change.

error_message: ['e', string]
    Server --> Client
    Indicates that something went wrong on the server.

    The client should probably print this to the chat.

status_message: ['u', string]
    Server --> Client
    Transmits some status from the server to the client. Similar to an
    error message.

    The client should probably print this to the chat.

settings_message: ['s', {{ ? }}]
    Server --> Client
    Sends terminal settings back to client. It should probably at least include
    fields 'cols' and 'rows', which are ints representing the terminal
    dimensions.

owner_message: ['~', int]
    Server --> Client
    Indicates who currently owns the console. Does not indicate a specific user
    but instead one of these three values:
        0 - nobody
        1 - you
        2 - someone who isn't you

ok_message: ['o']
    Server --> Client
    Noop message used when a command was acknowledged but the server has
    nothing to say.

cursor_message: ['_', x, y]
    Server --> Client
    Informs the client of the position of the cursor.

    This cannot be requested.

chat_message: [':', sender, message]
    Server --> Client
    Informs a client of a message from sender. The client should probably echo
    it into the chat.

    The server sends this message even to the client that sent the request
    triggering this response.

chat_request: [':', message]
    Server <-- Client
    Represents a chat message sent by a client.

    The chat system is used most obviously for chat between players, but really
    forms a more general command line for using webterm.

owner_request: ['~']
    Server <-- Client
    Represents a request for information on who the current owner is.

    The server should always respond with an owner_message.

---- Data ----

change_number: int
    Represents the index of a change. A client using HTTP should remember its
    most recent change number and send a change request for the changes
    following it as soon as possible.

change: [change_number, line_number, line]
    Represents a change in a line.

line_number: int
    Represents the number of a changed line.

line: [[ console_char | repetition_count ]]
    Represents a line of characters.

    See the documentation for repetition_count for more information about how
    repeats are usually specified.

repetition_count: int
    A number from one to infinity representing how many times the previous
    char should be repeated. The client should expand repeated characters while
    decoding the line.

    Some examples:
        ['a']
            expands to ['a']
        ['a', 1]
            expands to ['a', 'a']
            (1 additional repetition, 2 'a's)
        ['a', 4]
            expands to ['a', 'a', 'a', 'a', 'a']
            (4 additional repetitions, 5 'a's)

    1-indexing rather than 0-indexing was chosen for repetitions for clarity
    and because cases will very rarely arise that the extra byte has a real
    impact on the size of messages (especially given that most screens are less
    than 127 characters wide, eliminating all of these cases.)

console_char: bytestring | [bytestring, color_spec]
    (the lack of a list in the first group is intentional)

    Represents a character.

    If the color_spec is absent (the first form is used), then the char should
    be expanded to [data, 56] (in the second form), which corresponds to the
    default white-on-black scheme.

    For instance:
        'a'
            expands to ['a', 56]
        ['b', 40]
            expands to ['b', 40]

    The server should always prefer the smaller, first form if the character is
    white-on-black.

    The bytestring contains the character represented in utf-8. The client is
    responsible for decoding this to a native string representation.

color_spec: int
    The color specifier is a somewhat complicated int. It is always expressible
    as a uint16 although msgpack will take plenty of liberties with its size.
    Color specifiers are typically in [0, 128) and thus expressible as the
    smallest integer type in msgpack: the positive fixnum. A specifier may
    be larger if it uses unusual flags (typically italic, underscore,
    struck through, or reversed).

    The lowest three bits represent the background color, while the next three
    represent the foreground. The five bits above those represent five flags.

    Hence the form looks like this:
        [00000] [000] [000]
         |       |     + background color
         |       + foreground color
         + flags

    The flags are as follows.
        + bit 6 (1 << 0x6)  : whether character is bold
        + bit 7 (1 << 0x7)  : whether character is italic
        + bit 8 (1 << 0x8)  : whether character is underscored
        + bit 9 (1 << 0x9)  : whether character is struck through
        + bit A (1 << 0xA)  : whether character is reversed

    The colors match the following table:
        + black     : 0
        + red       : 1
        + green     : 2
        + brown     : 3
        + blue      : 4
        + magenta   : 5
        + cyan      : 6
        + white     : 7

    Although Pyte includes a provision for a default color, this protocol does
    not. As detailed above, though, the complete absence of a color specifier
    denotes the default color scheme (56 / 0x38 / white-on-black).
"""

def ChangeMessage(changes):
    return [
        "?", map(represent_change, changes)
    ]

def ScreenMessage(change_number, screen):
    return [
        "%", map(represent_line, screen), change_number
    ]

def HelloMessage():
    return [
        "h", "hello"
    ]

def ErrorMessage(error):
    return [
        "e", error
    ]

def StatusMessage(status):
    return [
        "u", status
    ]

def SettingsMessage(settings):
    return [
        "s", settings
    ]

def OkMessage():
    return ["o"]

def CursorMessage(cursor):
    return ["_", cursor.x, cursor.y]

def ChatMessage(sender, message):
    return [":", sender, message]

def OwnerMessage(owner_value):
    return ["~", owner_value]
NONE = 0
YOU = 1
NOT_YOU = 2
# ---- Data ----

def represent_change(change):
    change_number, line_number, line = change
    return [change_number, line_number, represent_line(line)]

def represent_line(line):
    out = []
    last_real = None
    for i in line:
        next_ = represent_char(i);
        if next_ == last_real:
            if isinstance(out[-1], int):
                out[-1] += 1
            else:
                out.append(1) # 1 repetition
        else:
            last_real = next_
            out.append(next_)
    return out

char_colors = {
    "black"     : 0,
    "red"       : 1,
    "green"     : 2,
    "brown"     : 3,
    "blue"      : 4,
    "magenta"   : 5,
    "cyan"      : 6,
    "white"     : 7,
    }

count = len(char_colors)

flag_bold           = 2 ** 6
flag_italics        = 2 ** 7
flag_underscore     = 2 ** 8
flag_strikethrough  = 2 ** 9
flag_reverse        = 2 ** 10

def represent_colorof(char):
    """
    Represents a character color as a single value. Usually this value is under
    256, but not always.
    """
    fg = char.fg if char.fg != "default" else "white"
    bg = char.bg if char.bg != "default" else "black"

    basic = char_colors[fg] * count + char_colors[bg]

    if char.bold            : basic |= flag_bold
    if char.italics         : basic |= flag_italics
    if char.underscore      : basic |= flag_underscore
    if char.strikethrough   : basic |= flag_strikethrough
    if char.reverse         : basic |= flag_reverse
    return basic

def represent_char(char):
    """
    Represents a Pyte-style Char.
    """
    cvalue = represent_colorof(char)
    dat = (char.data.encode("utf-8") if isinstance(char.data, unicode)
        else char.data)
    if cvalue == 56: # default color
        return char.data
    else:
        return [char.data, cvalue]
