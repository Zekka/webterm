from messages import ChatMessage, ErrorMessage, StatusMessage
from hashlib import sha1
from functools import wraps

import config

DEFAULT_RANK = -5

ADMIN_RANK = 101
ADMIN_PASS = "jj_-webterm_pass"

GUEST_PREFIX = ":"

ranked_tasks = {
    "grab control": 25,
    "free control": 25,
    "request control": 0,
    "do the impossible": 400
    }

with open("motd.txt") as f:
    MOTD = f.read().strip("\n")

class Chat(object):
    def __init__(self, state, socket_manager):
        self.app_state = state
        self.socket_manager = socket_manager
        self.commands = ChatCommands(self)
    def handle_join(self, client):
        self.greet(client)
        self.socket_manager.multicast(StatusMessage("%s has joined."
            % self.identify(client)))
    def handle_leave(self, client):
        self.socket_manager.multicast(StatusMessage("%s has left."
            % self.identify(client)))
        if client == self.find_owner():
            self.change_owner(None)
    def greet(self, client):
        client.status("Welcome to webterm.")
        client.status("Today's command is '%s'" % config.COMMAND)
        if self.is_authed(client):
            client.status(
                "You are currently authed as %s." % self.get_auth(client))
        else:
            client.status(
                "Please authenticate to access privileged commands.")
            client.status(
                "You currently appear to other users as %s."
                % self.identify(client))
        client.status(
            "To register or auth, please enter /register or /auth " +
            "respectively. For information about either of these, enter "+
            "/help register or /help auth.")
        client.status(
            "For general information about commands, enter /help."
            )
        client.status(
            "Press Tab to switch screens."
            )
        client.status(
            "==== Message of the Day ====")
        for i in MOTD.split("\n"):
            client.status(i)
    def handle_message(self, client, message):
        message = message.strip()
        if not message:
            return
        if message[0] == "/":
            return self.handle_command(client, message)
        broadcast_chat = ChatMessage(self.identify(client), message)
        self.socket_manager.multicast(broadcast_chat)
    def handle_command(self, client, cmdstr):
        cmd_stripped = cmdstr[1:]
        cmd, _, argstr = cmd_stripped.partition(" ")
        argstr = argstr.split()
        return self.commands.run(cmd, client, argstr)
    def is_authed(self, client):
        return "name" in client.data
    def get_auth(self, client):
        return client.data["name"]
    def approve_auth(self, client, name):
        self.socket_manager.multicast(StatusMessage(
            "%s has authed as %s" % (self.identify(client), name)
            ))
        client.data["name"] = name
        if self.find_owner() == client:
            client.status("(They are still arbiter.)")
    def identify(self, client):
        """
        Returns the client's name if he's currently authed for one, or else an
        automatically generated one.
        """
        if self.is_authed(client):
            return self.get_auth(client)
        else:
            return GUEST_PREFIX + "guest-%s" % sha1(str(id(client))).hexdigest()[:5]
            # TODO: Use something that identifies the client between separate
            # loads of the webpage.
    def find_owner(self):
        return self.app_state.owner
    def change_owner(self, new):
        old = self.find_owner()
        if old == new:
            return

        if old and new:
            msg = "Arbiter changed from %s to %s." % (
                    self.identify(old),
                    self.identify(new),
                )
        elif new:
            msg = "%s is now arbiter." % (
                    self.identify(new),
                )
        elif old:
            msg = "%s is no longer arbiter." % (
                    self.identify(old)
                )

        self.socket_manager.multicast(StatusMessage(msg))
        self.app_state.change_owner(new)

def reqrank(rank):
    if rank in ranked_tasks:
        action = rank
        required_rank = ranked_tasks[action]
    elif isinstance(rank, tuple) and len(rank) == 2:
        action, required_rank = rank
    elif isinstance(rank, int):
        action = "use this command"
        required_rank = rank
    else:
        raise ValueError("could not interpret %s as a valid rank" % rank)

    fail_message = ("You must have at least rank %s to %s."
        % (required_rank, action)
    )

    def dec(f):
        @wraps(f)
        def _f(self, client, *args, **kwargs):
            client_rank = Account.get_rank(self.chat.identify(client))
            if client_rank < required_rank:
                return ErrorMessage("%s Your current rank is %s."
                    % (fail_message, client_rank,)
                )
            return f(self, client, *args, **kwargs)
        _f.__doc__ = (textwrap.dedent(_f.__doc__).strip() +
            "\n\n%s" % fail_message
        )
        return _f
    return dec

import traceback
import textwrap
class ChatCommands(object):
    def __init__(self, chat):
        self.chat = chat
    def run(self, cmd, client, args):
        name = cmd.lower()
        try:
            cmdfunc = getattr(self, "cmd_%s" % name)
        except AttributeError:
            return ErrorMessage("No command %s exists." % cmd)
        try:
            return cmdfunc(client, *args)
        except TypeError, e:
            print "A TypeError occurred during command %s." % cmd
            traceback.print_exc()
            return ErrorMessage("Incorrect arguments to command or internal error."
                + " have the maintainer check the logs if you're sure you"
                + " didn't screw up.")
        except Exception, e:
            print "Some exception occurred during command %s." % cmd
            traceback.print_exc()
            return ErrorMessage("An exception occurred during command."
                + " Bother the maintainer to fix it.")
    def cmd_help(self, client, cmd = None):
        """
        /help [cmd]
        Displays help for a given command, or else lists all commands if none is specified.
        """
        if cmd == None:
            return self.cmd_list(client)
        cmd = cmd.lower()
        try:
            cmdfunc = getattr(self, "cmd_%s" % cmd)
        except AttributeError:
            return ErrorMessage("No command %s exists." % cmd)
        doc = textwrap.dedent(cmdfunc.__doc__.strip())
        for i in doc.split("\n"):
            client.status(i)
    def cmd_list(self, client):
        """
        /list
        Lists available commands.
        """
        prefix = "cmd_"
        cmds = [i[len(prefix):] for i in dir(self) if i.startswith(prefix)]
        return StatusMessage("Currently availiable commands are %s"
            % ", ".join(cmds))
    def cmd_register(self, client, username, password):
        """
        /register username password
        Registers the given username with the given password. While passwords are case-sensitive, usernames are not. After registration you should log in with /auth.
        """
        try:
            Account.create(username, password)
            return StatusMessage("Registration complete: you may now /auth.")
        except AccountError, e:
            return ErrorMessage("Registration failed: %s" % e.message)
        except ValueError, e:
            return ErrorMessage(e.message)
    def cmd_auth(self, client, username, password):
        """
        /auth username password
        Authenticates with the given username/password pair. While passwords are case-sensitive, usernames are not. Success will change your displayed username to the username passed, preserving case.
        """
        if Account.check_auth(username, password):
            self.chat.approve_auth(client, username)
        elif Account.exists(username):
            client.error(
                "That is not the password for that account.")
        else:
            client.error("That is not a real account.")
    def cmd_rank(self, client, username = None, rank = None):
        """
        /rank [username] [newrank]
        Displays the rank of the user with the given username. If no username is given, displays your rank. If a new rank is given, assigns the new rank.
        """
        if username == None:
            username = self.chat.identify(client)
        if not rank:
            caller = self.chat.identify(client)
            acct_rank = Account.get_rank(username)
            return StatusMessage("%s has rank %s." % (username, acct_rank))
        new_rank = int(rank)
        acct = Account.find_user(username)
        client_rank = Account.get_rank(self.chat.identify(client))
        if not acct:
            return ErrorMessage("No such account was found. As a security"
                + " precaution, rank cannot be assigned to accounts that have"
                + " not been created and given password")
        if acct.rank >= client_rank:
            return ErrorMessage("That user's rank is currently greater than or"
                + " equal to yours. Ask somebody of greater rank to make the"
                + " change instead.")
        if new_rank >= client_rank:
            return ErrorMessage("The rank you are attempting to give that user"
                + " is greater than your current rank. Ask somebody of greater"
                + " rank to make the change instead.")
        acct.rank = int(new_rank)
        return StatusMessage("Rank of user %s is now %s." % (username, acct.rank))
    @reqrank("grab control")
    def cmd_grab(self, client):
        """
        /grab
        The forceful alternative to /take: for real men only.
        Attempts to forcefully grab control of the console from whoever currently has it. That person immediately loses control. Can only be used on others who are lower-ranking.
        You can use /take if you want webterm to automatically decide between /grabbing and /asking.
        """
        rank = Account.get_rank(self.chat.identify(client))
        rank_other = (
            Account.get_rank(
                self.chat.identify(self.chat.find_owner())
                )
            if self.chat.find_owner() else
                0
        )
        if rank < rank_other:
            return ErrorMessage("The current arbiter outranks you.")
        self.chat.socket_manager.multicast(StatusMessage(
            "%s has grabbed control." % (self.chat.identify(client))
            )
        )
        self.chat.change_owner(client)
    @reqrank("request control")
    def cmd_ask(self, client):
        """
        /ask
        The gentle alternative to /grab: for women and hippies.
        Takes control of the console only if nobody else has it. 
        You can use /take if you want webterm to automatically decide between /grabbing and /asking.
        """
        if self.chat.find_owner():
            return ErrorMessage("Someone is already the arbiter.")
        self.chat.socket_manager.multicast(StatusMessage(
            "%s has requested control." % (self.chat.identify(client))
            )
        )
        self.chat.change_owner(client)
    def cmd_take(self, client):
        """
        /take
        /grabs control of the console if someone already has it, but /asks if nobody does.
        This is the most general command to take control of the console.
        Rank restrictions on /grab and /ask apply.
        """
        if self.chat.find_owner():
            return self.cmd_grab(client)
        else:
            return self.cmd_ask(client)
    def cmd_drop(self, client):
        """
        /drop
        Releases control of the console if you have it.
        """
        if self.chat.find_owner() != client:
            return ErrorMessage("You do not control the console.")
        self.chat.socket_manager.multicast(StatusMessage(
            "%s has dropped control." % (self.chat.identify(client))
            )
        )
        self.chat.change_owner(None)
    @reqrank("free control")
    def cmd_free(self, client):
        """
        /free
        Releases control of the console from whoever has it. This is similar to
        a /grab followed by a /drop.
        """
        owner = self.chat.find_owner()
        if not owner:
            return ErrorMessage("The console is already free.")
        
        rank = Account.get_rank(self.chat.identify(client))
        rank_other = (
            Account.get_rank(
                self.chat.identify(owner)
                )
            if owner else
                0
        )

        if rank < rank_other:
            return ErrorMessage("The current arbiter outranks you.")

        self.chat.socket_manager.multicast(StatusMessage(
            "%s has freed the console." % (self.chat.identify(client))
            )
        )
        self.chat.change_owner(None)
    def cmd_arbiter(self, client):
        """
        /arbiter
        Displays the current arbiter.
        """
        owner = self.chat.find_owner()
        if not owner:
            return StatusMessage("Nobody is currently arbiter.")
        return StatusMessage("The arbiter is %s." % self.chat.identify(owner))

"""
Storage for the auth subsystem.
"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import atexit

import os

engine = create_engine("sqlite:///webterm.db")
engine.raw_connection().connection.text_factory = str

Session = sessionmaker(bind=engine)
session = Session()
atexit.register(session.commit)

Base = declarative_base()

def hash_password(salt, password):
    return unicode(sha1(unicode(password) + unicode(salt)).hexdigest())

class AccountError(Exception): pass

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key = True)
    name = Column(String, unique = True)
    password_hash = Column(String)
    salt = Column(String(24))
    rank = Column(Integer, default = DEFAULT_RANK)

    @classmethod
    def create(cls, username, password):
        if username.startswith(GUEST_PREFIX):
            raise ValueError("That is not an appropriate name for an account.")
        if cls.exists(username):
            raise AccountError("Account %s already exists." % username)
        salt ="".join(["%02X" % ord(x) for x in os.urandom(12)])
        phash = hash_password(salt, password)
        g = cls(name=username.lower(), salt = salt, password_hash = phash)
        session.add(g)
        return g
    @classmethod
    def find_user(cls, username):
        return (session.query(cls)
                .filter_by(name = username.lower())
                .first())
    @classmethod
    def exists(cls, username):
        return cls.find_user(username) != None
    @classmethod
    def check_auth(cls, username, password):
        u = cls.find_user(username)
        if not u: return False
        return u.password_hash == hash_password(u.salt, password)
    @classmethod
    def get_rank(cls, username):
        u = cls.find_user(username)
        if not u:
            return DEFAULT_RANK
        return u.rank
    def set_password(self, password):
        self.password_hash = hash_password(self.salt, password)

Base.metadata.create_all(engine)

admin = Account.find_user("admin")
if not admin:
    admin = Account.create("admin", ADMIN_PASS)
admin.set_password(ADMIN_PASS)
admin.rank = ADMIN_RANK
