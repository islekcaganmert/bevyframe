from bevyframe import *

blacklist = lambda: ["demo@hereus.net"]


def get(request: Request) -> (Page, Response):
    if request.email.split('@')[0] == 'Guest':
        return redirect('/login.py')
    return Page(
        title='BevyFrame Test App',
        description='BevyFrame Test App',
        selector=f'body_{request.user.id.settings.theme_color}',
        childs=[
            Title(f'Hello, {request.user.id.name} {request.user.id.surname} from {request.user.network}!'),
            Box(
                width=Size.max_content,
                text_align=Align.center,
                childs=[
                    Line([Textbox('', type="text", placeholder='textbox')]),
                    Line([Button(innertext='Button')]),
                    Line([Button(selector='small', innertext='Button')]),
                    Line([Button(selector='mini', innertext='Button')])
                ]
            )
        ]
    )
