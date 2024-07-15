from typing import Any
import getpass
import os
from bevyframe.Objects.Response import Response
import requests
import TheProtocols
import json
from bevyframe.Frame.error_handler import error_handler
from bevyframe.Frame.route import route
from bevyframe.Frame.Run.Booting import booting
from bevyframe.Frame.Run.Receiver import receiver
from bevyframe.Frame.Run.Responser import responser
from bevyframe.Frame.Run.Sender import sender


class Frame:
    def __init__(self, package, developer, administrator, secret, style, icon='/favicon.ico', keywords=None) -> None:
        if keywords is None:
            keywords = []
        self.secret = secret
        self.package = package
        self.debug = False
        self.developer = developer
        self.routes = {}
        if isinstance(style, dict):
            self.style = style
        elif isinstance(style, str):
            if os.path.isfile(style):
                self.style = json.load(open(style, 'rb'))
            elif style.startswith('https://'):
                r = requests.get(style)
                if r.status_code == 200:
                    self.style = r.json()
                else:
                    self.style = {}
            else:
                self.style = {}
        else:
            self.style = {}
        self.icon = icon
        self.keywords = keywords
        if administrator:
            self.admin = TheProtocols.ID(administrator, getpass.getpass(f'Password for {administrator}: '))
            print()
            print(f"Welcome {self.admin.id}!")
        print()

    def error_handler(self, request, status_code, exception) -> Response:
        return error_handler(self, request, status_code, exception)

    def route(self, path, whitelist: list = None, blacklist: list = None) -> Any:
        return route(self, path, whitelist, blacklist)

    def run(self, host: str = '127.0.0.1', port: int = 5000, debug: bool = True):
        server_socket = booting(self, host, port, debug)
        try:
            while True:
                recv, client_socket = receiver(self, server_socket)
                resp = responser(self, recv)
                sender(self, recv, resp, client_socket)
        except KeyboardInterrupt:
            server_socket.close()
            print('\r  \nServer was been terminated!\n')