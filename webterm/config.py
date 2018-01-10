commands = {
    # Add your own! (Mine won't work for you.)
    "lcs": {
        "command"       : "/home/vinegareater/games/lcs/crimesquad",
        "working_dir"   : "/home/vinegareater/games/lcs/",
    },
    "df": {
        "command"       : "/home/vinegareater/games/df/df",
        "working_dir"   : "/home/vinegareater/games/df/",
    },
    "vim": {
        "command"       : "/home/vinegareater/programs/chrootvim/vim",
        "working_dir"   : "/home/vinegareater/programs/chrootvim/"
    }
}
ACTIVE_COMMAND = "lcs"

COMMAND = commands[ACTIVE_COMMAND]["command"]
WORKING_DIR = commands[ACTIVE_COMMAND]["working_dir"]
ARGS = []
MAX_CHANGES = 1024
ROWS = 30
COLS = 80

PORT = 5000
# You're going to want to change this.
SECRET_KEY = '\x03\xd4\x8f~\x00\xc4\xde.\x15}\xaf-\x8e!S"\xdb\xcd\xc5\xe7\x051\xf8\x1e'
