#!/usr/bin/python

import argparse
import webterm.config as config
from socketio.server import SocketIOServer

def main(ip, port, cmd):
    # this is a bit of a hack
    config.COMMAND = cmd

    from webterm.app import app
    SocketIOServer((ip, port), app, resource='socket.io').serve_forever()

if __name__ == "__main__":
    import sys
    parser = argparse.ArgumentParser("webterm", description = 'webterm: a multiuser terminal',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-p'    , '--port'      , type=int, default=config.PORT         , help="port to run server on")
    parser.add_argument('-i'    , '--ip'        , type=str, default="0.0.0.0"           , help="IP to listen on")
    parser.add_argument('-c'    , '--command'   , type=str, default=config.COMMAND      , help="command to run")

    g = parser.parse_args()
    ip = g.ip
    port = g.port
    command = g.command
    main(ip, port, command)
