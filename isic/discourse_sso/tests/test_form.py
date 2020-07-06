from isic.discourse_sso.forms import DiscourseSSOLoginForm


def test_sso_login_form(client, girder_user, monkeypatch):
    def _get_girder_user(*args, **kwargs):
        return girder_user

    monkeypatch.setattr(DiscourseSSOLoginForm, '_get_girder_user', _get_girder_user)

    def _get_girder_user_groups(*args, **kwargs):
        return [
            {'name': 'a-group'},
            {'name': 'another-group'},
        ]

    monkeypatch.setattr(DiscourseSSOLoginForm, '_get_girder_user_groups', _get_girder_user_groups)

    form = DiscourseSSOLoginForm(data={'login': 'some-login', 'password': 'foo'})
    assert form.is_valid(), form.errors
