import djclick as click

from isic.login.backends import GirderBackend
from isic.login.girder import get_girder_db


@click.command(help='Pull in all users from Girder to Django')
def pull_girder_users():
    girder_users = list(get_girder_db()['user'].find())
    with click.progressbar(girder_users) as bar:
        for girder_user in bar:
            GirderBackend.get_or_create_user_from_girder(girder_user)
