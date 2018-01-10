from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, Response
from flask import request

from socketio import socketio_manage
from socketio.server import SocketIOServer
from socketio.namespace import BaseNamespace
from werkzeug.serving import run_with_reloader

from termsess import TerminalSession
from util import synchronized, Category
from messages import (ChangeMessage, ScreenMessage, HelloMessage, ErrorMessage,
        StatusMessage, SettingsMessage, OkMessage, CursorMessage, OwnerMessage,
        pack, unpack)
import messages

from collections import deque

import time
from chat import Chat

from config import *

from threading import Thread # Must happen *after* monkeypatching

app = Flask(__name__)
app.secret_key = (
    SECRET_KEY
)

class ChangeTable(object):
    def __init__(self, maxchanges):
        self.maxchanges = maxchanges
        self.offset = 0
        self.changes = []
        self.next_idx = 0
    def has_change(self, number):
        return (number > self.offset
            and number < self.offset + len(self.changes))
    def add_change(self, line_number, line):
        if len(self.changes) == self.maxchanges:
            self.changes = self.changes[1:]
            self.offset += 1
        self.changes.append((self.next_idx, line_number, line,))
        self.next_idx += 1
    def changes_after(self, change_number):
        return self.changes[change_number - self.offset:]

appstate = Category()

class AppState(object):
    def __init__(self):
        self.session = None
        self.changes = ChangeTable(MAX_CHANGES)
        self.subscribers = []
        self.chat = Chat(self, ApiNamespace)
        self.owner = None

    @synchronized(appstate)
    def start(self):
        if self.session:
            return
        self.session = TerminalSession(COMMAND, ARGS, WORKING_DIR,
            rows=ROWS, cols=COLS, restart=True)
        self.session.start(self.add_change, self.move_cursor)
        self.start_processdaemon()

    def start_processdaemon(self):
        Thread(target = self.processdaemon).start()
        # cheat at getting fast updates

    def processdaemon(self):
        last_cursor = self.session.screen.cursor
        while True:
            self.session.process()
            time.sleep(0.01)
            new_cursor = self.session.screen.cursor
            if (last_cursor.x != new_cursor.x or
                last_cursor.y != new_cursor.y):
                self.move_cursor(new_cursor)
            last_cursor = new_cursor

    def api_handle(self, client, message):
        handlers = {
            "?": self.handle_change_request,
            "%": self.handle_screen_request,
            "s": self.handle_settings_request,
            "h": self.handle_hello_request,
            "k": self.handle_keypress_request,
            "l": self.handle_leave_request,
            ":": self.handle_chat_request,
            "~": self.handle_owner_request,
            }

        if not self.session:
            self.start()
        self.session.process()
        tag, args = message[0], message[1:]
        try:
            hndlr = handlers[tag]
        except KeyError:
            return ErrorMessage("unrecognized request: %s" % tag) 
        return hndlr(client, *args)

    @synchronized(appstate)
    def add_change(self, line_number, line):
        idx = self.changes.next_idx
        self.changes.add_change(line_number, line)
        for i in self.subscribers:
            i.change(idx, line_number, line)

    @synchronized(appstate)
    def move_cursor(self, cursor):
        for i in self.subscribers:
            i.cursor(cursor)

    def add_subscriber(self, other):
        self.subscribers.append(other)

    def handle_change_request(self, client, change_number):
        if not self.changes.has_change(change_number):
            return self.handle_screen_request(None)
        changes = self.changes.changes_after(change_number)
        out = {}
        for i in changes:
            line_number = i[1]
            out[line_number] = i
        changes = sorted(out.values(), key = lambda i: i[1])
        return ChangeMessage(changes)

    @synchronized(appstate)
    def handle_screen_request(self, client):
        return ScreenMessage(self.changes.next_idx, self.session.screen)

    def handle_settings_request(self, client):
        return SettingsMessage({
            "rows": ROWS,
            "cols": COLS
        })

    @synchronized(appstate)
    def handle_keypress_request(self, client, key):
        if client != self.owner:
            return ErrorMessage("You are not the current arbiter.")
        self.session.input_bytes(key)
        self.session.process()
        return OkMessage()
        
    def handle_hello_request(self, client, hello):
        self.chat.handle_join(client)
        return HelloMessage()

    def handle_chat_request(self, client, message):
        g = self.chat.handle_message(client, message)
        return g if g else OkMessage()

    def handle_leave_request(self, client):
        g = self.chat.handle_leave(client)
        client.disconnect()
        return g if g else OkMessage()

    def handle_owner_request(self, client):
        if self.owner == client:
            return OwnerMessage(messages.YOU)
        elif self.owner:
            return OwnerMessage(messages.NOT_YOU)
        else:
            return OwnerMessage(messages.NONE)
    def change_owner(self, new):
        self.owner = new
        for i in ApiNamespace.list_clients():
            i.msg(self.handle_owner_request(i))

class ApiNamespace(BaseNamespace):
    sockets = {}
    def initialize(self):
        self.data = {}
    def recv_connect(self):
        type(self).sockets[id(self)] = self
    def recv_message(self, data):
        unpacked = unpack(data)
        id_ = unpacked["id"]
        response = state.api_handle(self, unpacked["request"])
        self.send(pack({
            "id"        : id_,
            "response"  : response
        }))
    def disconnect(self, *args, **kwargs):
        if id(self) in type(self).sockets:
            del type(self).sockets[id(self)]
            state.handle_leave_request(self)
    @classmethod
    def change(cls, change_number, line_number, newline):
        cls.multicast(state.handle_change_request(None, change_number))
    @classmethod
    def cursor(cls, cursor):
        cls.multicast(CursorMessage(cursor))
    @classmethod
    def multicast(cls, message):
        for i in cls.list_clients():
            i.msg(message)
    def msg(self, message):
        self.send(pack({
            "response"  : message
        }))
    def status(self, statusmessage):
        self.msg(StatusMessage(statusmessage))
    def error(self, errormessage):
        self.msg(ErrorMessage(errormessage))
    @classmethod
    def list_clients(cls):
        return cls.sockets.values()
state = AppState()
state.add_subscriber(ApiNamespace)

@app.route("/socket.io/<path:rest>")
def socket_api(rest):
    socketio_manage(request.environ, {"/api": ApiNamespace}, request)
    return "" # deal with view function greenlet error

@app.route("/")
def hello():
    return render_template("main.html")

@app.route("/style/")
def style():
    return Response(render_template("style.css"), mimetype='text/css')


