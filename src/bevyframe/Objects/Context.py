import urllib.parse

from TheProtocols import *
from typing import Any, Callable
import json
import jinja2
import os
from bevyframe.Features.Database import Database
from bevyframe.Objects.Response import Response
from bevyframe.Widgets.Page import Page
from bevyframe.Helpers.LazyInitDict import LazyInitDict


def lazy_init_data(con) -> Callable[[Any], None]:
    def initialize(self) -> None:
        self._data = con.user.data()
    return initialize


def lazy_init_pref(con) -> Callable[[Any], None]:
    def initialize(self) -> None:
        self._data = con.user.preferences()
    return initialize


class Browser:
    def __init__(self, headers: dict) -> None:
        self.language = headers.get('Accept-Language', 'en-US').split(',')[0].split(';')[0].strip()
        self.ram = headers.get('Device-Memory', 0)
        self.bandwidth = headers.get('Downlink', 0)
        self.network_profile = headers.get('ECT', 'NotGiven')
        self.user_agent = ua = headers.get('User-Agent', 'Mozilla/5.0 (;) AppleWebKit/0.0 (KHTML, like Gecko) Chrome/0.0.0.0 Safari/0.0)')
        try:
            ua = ua.removeprefix(ua.split('(')[0] + '(')
            self.device = ua.split(')')[0]
            ua = ua.removeprefix(self.device + ')').removeprefix(' AppleWebKit/')
            self.webkit_version = ua.split('(')[0]
            ua = ua.split(')')[1].removeprefix(' ')
            self.name = ua.split('/')[0]
            self.version = ua.split('/')[1].split(' ')[0]
        except IndexError:
            self.device = ''
            self.os = ''
            self.webkit_version = 'NotCompatible'
            self.name = 'Hidden'
            self.version = ''


class Context:
    def __init__(self, data: dict, app) -> None:
        self.method = data['method']
        self.path = data['path'].split('?')[0]
        self.headers = data['headers']
        self.browser = Browser(self.headers)
        self.ip = data.get('ip', '127.0.0.1')
        self.query = {}
        self.env = app.environment() if callable(app.environment) else app.environment
        if not isinstance(self.env, dict):
            self.env = {}
        self.tp = app.tp
        while data['body'].endswith('\r\n'):
            data['body'] = data['body'].removesuffix('\r\n')
        while data['body'].startswith('\r\n'):
            data['body'] = data['body'].removeprefix('\r\n')
        self.body = urllib.parse.unquote(data['body'].replace('+', ' '))
        self.form = {}
        for b in data['body'].split('\r\n'):
            for i in b.split('&'):
                if '=' in i:
                    self.form.update({
                        urllib.parse.unquote(i.split('=')[0].replace('+', ' ')): urllib.parse.unquote(i.split('=')[1].replace('+', ' '))
                    })
        if '?' in data['path']:
            for i in data['path'].split('?')[1].split('&'):
                if '=' in i:
                    self.query.update({
                        urllib.parse.unquote(i.split('=')[0].replace('+', ' ')): urllib.parse.unquote(i.split('=')[1].replace('+', ' '))
                    })
                else:
                    self.query.update({
                        urllib.parse.unquote(i): True
                    })
        try:
            self.email = data['credentials']['email']
            self.token = data['credentials'].get('token', None)
            self.password = data['credentials'].get('password', None)
        except KeyError:
            self.email = 'Guest@' + app.default_network
            self.token = ''
        self._user = None
        self.data = LazyInitDict(lazy_init_data(self))
        self.preferences = LazyInitDict(lazy_init_pref(self))
        self.app = app
        self.tp: TheProtocols = app.tp
        self.cookies = {}
        if 'Cookie' in self.headers:
            for cookie in self.headers['Cookie'].split('; '):
                if '=' in cookie:
                    self.cookies.update({cookie.split('=')[0]: cookie.split('=')[1]})

    @property
    def db(self) -> Database:
        return self.app.db

    @property
    def user(self) -> Session:
        if self._user is None:
            try:
                if self.email.split('@')[0] == 'Guest':
                    self._user = self.tp.create_session(f'Guest@{self.app.default_network}', '')
                elif self.token:
                    self._user = self.tp.restore_session(self.email, self.token)
                else:
                    self._user = self.tp.create_session(self.email, self.password)
            except CredentialsDidntWorked:
                self._user = self.tp.create_session(f'Guest@{self.app.default_network}', '')
            except NetworkException:
                self._user = self.tp.create_session(f'Guest@{self.app.default_network}', '')
        return self._user

    def render_template(self, template: str, **kwargs) -> (Response, str):
        functions = '''
            const _bridge = (func, ...args) => {
                fetch(`${location.protocol}//${location.host}/.well-known/bevyframe/proxy`,{
                    method:'POST',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({func:func,args:args})
                }).then(res => res.json()).then(data => {
                    if (data.error) {throw new Error(data.error);}
                    else if (data.type === 'return') {return data.value;}
                    else if (data.type === 'script') {eval(data.value);}
                    else if (data.type === 'view') {
                        if (data.element === 'body') {document.body.innerHTML = data.value;}
                        else {document.querySelector(data.element).innerHTML = data.value;}
                    }
                }).catch(err => {  });
            };
        '''
        for i in os.listdir('./functions/'):
            if i.endswith('.py'):
                i = i[:-3]
                functions += " const " + i + " = (...args) => {_bridge('" + i + "', ...args)};"
        functions = (functions
                     .replace('    ', '')
                     .replace('  ', ' ')
                     .replace('\n', '')
                     .strip())
        with open("./pages/" + template.removeprefix('/')) as f:
            html = f.read()
            if '<body' in html:
                prop = html.split('<body')[1].split('>')[0].split(' ')
                for i in prop:
                    if i.split('=')[0] == 'login_required' and self.email.split('@')[0] == 'Guest':
                        return self.start_redirect(f"/{self.app.loginview.removeprefix('/')}")
            return jinja2.Template(html).render(
                context=self,
                style=f"<style>{self.app.style}</style>",
                functions=f"<script>{functions}</script>",
                safe=lambda x: x.replace('<', '&lt;').replace('>', '&gt;'),
                **kwargs
            )

    def create_response(
            self,
            body: (Page, str, dict, list) = '',
            credentials: dict = None,
            headers: dict = None,
            status_code: int = 200
    ) -> Response:
        if credentials is None:
            credentials = {'email': self.email, 'token': self.token}
        if credentials['token'] is None:
            credentials = {'email': self.email, 'password': self.password}
        return Response(
            body,
            headers=headers if headers is not None else {'Content-Type': 'text/html; charset=utf-8'},
            credentials=credentials,
            status_code=status_code,
            app=self.app
        )

    def start_redirect(self, to_url) -> Response:
        return self.create_response(
            headers={'Location': to_url},
            status_code=303,
            credentials={'email': self.email, 'token': self.token}
        )

    @staticmethod
    def get_asset(path: str) -> str:
        return "/assets/" + path

    @property
    def json(self) -> Any:
        return json.loads(self.body)
