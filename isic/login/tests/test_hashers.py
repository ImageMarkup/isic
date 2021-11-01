from django.contrib.auth.hashers import check_password, make_password


def test_girder_password_hasher_encode():
    hashed = make_password('secret', hasher='bcrypt_girder')

    assert hashed.startswith('bcrypt_girder$')


def test_girder_password_hasher_decode_correct():
    hashed = make_password('secret', hasher='bcrypt_girder')

    check = check_password('secret', hashed)

    assert check is True


def test_girder_password_hasher_decode_incorrect():
    hashed = make_password('secret', hasher='bcrypt_girder')

    check = check_password('wrong', hashed)

    assert check is False
