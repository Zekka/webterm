import pyte
import pty, os, subprocess
import termios
import select
import time
import fcntl
import struct
from cStringIO import StringIO
import os.path
class SessionStateError(Exception): pass

class TerminalSession(object):
    def __init__(self, cmd, args, working_dir, **params):
        if not params.get("rows"): params["rows"] = 25
        if not params.get("cols"): params["cols"] = 80
        if not params.get("restart"): params["restart"] = False

        self.cmd = cmd
        self.args = [cmd] + args
        self.working_dir = working_dir
        self.params = params
        self.running = False

        self.actual_dir = os.getcwd()
        self.home_dir = os.path.join(self.actual_dir, "home")

    def start(self, evtcallback, cursorcallback):
        """
        Launches the TerminalSession's process and adds to it the given
        callback to deal with modified lines.

        The callback takes the form callback(line_number, line).
        """
        if self.running:
            raise SessionStateError("TerminalSession already running")

        self.running = True

        self.stream = pyte.ByteStream()
        self.screen = pyte.DiffScreen(self.params["cols"], self.params["rows"])
        # self.screen.set_mode(pyte.modes.LNM) # This treats \ns as \r\ns.
            # Is this necessary/reasonable?
        self.stream.attach(self.screen)

        child_pid, self.child_fd = pty.fork()
                       
        os.chdir(self.working_dir)
        os.environ['HOME'] = self.home_dir
        if not child_pid: # under what circumstances would it not be 0?
            os.execv(self.cmd, self.args)

        attr = termios.tcgetattr(self.child_fd)
        attr[3] = attr[3] & ~termios.ECHO # Disable echoing
        termios.tcsetattr(self.child_fd, termios.TCSANOW, attr)

        winsize = struct.pack("HHHH", self.params["rows"], self.params["cols"],
            0, 0)
        fcntl.ioctl(self.child_fd, termios.TIOCSWINSZ, winsize) # set size


        self.callback = evtcallback
        self.cursor_callback = cursorcallback


    def end(self):
        self.running = False
        if self.params["restart"]:
            self.start(self.callback, self.cursor_callback)

    def process(self):
        if not self.running:
            raise SessionStateError("TerminalSession closed or never opened")

        was_at_some_time_ready = False

        output = StringIO()
        try:
            while select.select([self.child_fd], [], [], 0.0)[0]:
                was_at_some_time_ready = True
                s = os.read(self.child_fd, 1)
                if len(s) == 0: # EOF
                    self.end()
                    break

                output.write(s)
        except OSError: # this occasionally means EOF
            pass


        if was_at_some_time_ready:
            g = output.getvalue()
            self.stream.feed(g)
            if len(g) == 0: self.end() # EOF.
        
            while self.screen.dirty:
                line_number = self.screen.dirty.pop()
                self.callback(line_number, self.screen[line_number])

            self.cursor_callback(self.screen.cursor)
        else:
            time.sleep(0.01) # wait a sec to avoid wasting CPU
            # TODO: used this in the threaded version, is it necessary in the
            # non-threaded one?
            pass

    def ready(self):
        return self.running
    def keypress(self, keycode):
        return self.input_text(chr(keycode))
    def input_text(self, s):
        remaining = s
        while remaining:
           amt = os.write(self.child_fd, remaining)
           if amt == 0:
               self.end()
               return
           remaining = remaining[amt:]
    def input_bytes(self, b):
        self.input_text("".join(map(chr, b)))
if __name__ == "__main__":
    import pdb
    from messages import ChangeMessage

    g = TerminalSession("/usr/bin/vim", [])


    change_num = 0
    
    def hexify(s):
        return " ".join(map(lambda i: "{0:02x}".format(ord(i)), s))

    def handle_line(line_no, line):
        global change_num

        rep = ChangeMessage(change_num, line_no, line)
        change_num += 1
        print "{0:02}: {1}".format(len(rep), hexify(rep)[:123])
        """
        print "{0:02}  {1}".format(
            line_no, "".join(map(lambda i: i.data, line)))
        print "    {0}".format("".join(map(lambda i:i.fg[0], line)))
        """
    g.start(handle_line)
    while g.ready():
        g.process()
