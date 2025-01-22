import logging

from django.template import Context, Template
import pytest

from isic.core.templating import MissingVariableError


@pytest.mark.parametrize(
    "template",
    ["{{ name }}", "{{ name|default:'foo' }}", "{% if not name %}{% endif %}"],
    ids=["missing-variable", "missing-variable-with-default", "missing-variable-with-if"],
)
def test_missing_variable(caplog, template):
    template = Template(template, name="index.html")
    context = Context({})

    with caplog.at_level(logging.DEBUG, logger="django.template"):
        template.render(context)

    assert len(caplog.records) == 1
    assert caplog.records[0].level == logging.ERROR
    assert (
        caplog.records[0].getMessage()
        == "Exception while resolving variable 'name' in template 'index.html'."
    )


def test_missing_variable_ninja_excluded(settings, monkeypatch):
    settings.RAISE_MISSING_TEMPLATE_VARIABLES = True

    template = Template("{{ name }}", name="foo.html")

    with pytest.raises(MissingVariableError):
        template.render(Context({}))

    def extract_stack():
        return [
            type("Frame", (), {"filename": "ninja/schema.py"}),
            type("Frame", (), {"filename": "isic/core/templating.py"}),
        ]

    monkeypatch.setattr("isic.core.templating.traceback.extract_stack", extract_stack)

    # this should not raise an exception
    template.render(Context({}))


@pytest.mark.parametrize(
    ("template", "raises_exception"),
    [
        ("{{ name }}", True),
        ("{{ name|default:'foo' }}", True),
        ("{% if name %}{{ name }}{% endif %}", True),
        # this is currently one of the unsupported cases since IfNot catches all exceptions
        ("{% if not name %}{% endif %}", False),
    ],
    ids=[
        "missing-variable",
        "missing-variable-with-default",
        "missing-variable-with-if",
        "missing-variable-with-if-not",
    ],
)
def test_missing_variable_raises_exception(settings, template, raises_exception):
    settings.RAISE_MISSING_TEMPLATE_VARIABLES = True

    template = Template(template, name="index.html")
    context = Context({})

    if raises_exception:
        with pytest.raises(MissingVariableError):
            template.render(context)
    else:
        template.render(context)
