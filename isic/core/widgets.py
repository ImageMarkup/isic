import json
from typing import Any

from django import forms


class DiagnosisPicker(forms.Select):
    template_name = "core/widgets/diagnosis_picker.html"

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        # store the choice values for an easier way to perform template
        # rendering of the entire DiagnosisEnum.
        context["diagnosis_values"] = {choice[1]: choice[0] for choice in self.choices}

        # set the default so templates won't complain about undefined variables
        context.setdefault("value", None)
        return context


class MultiselectPicker(forms.CheckboxSelectMultiple):
    template_name = "core/widgets/multiselect_picker.html"

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["choice_list"] = [{"pk": choice[0], "text": choice[1]} for choice in self.choices]
        context["widget_value_id"] = f"multiselect-value-{name}"
        context["choice_list_id"] = f"multiselect-choices-{name}"
        return context


class ComboboxWidget(forms.Select):
    template_name = "core/widgets/combobox.html"

    def __init__(
        self,
        queryset,
        lookup_field="name",
        option_type="option",
        edit=False,  # noqa: FBT002
        attrs=None,
    ):
        super().__init__(attrs)
        self.queryset = queryset
        self.lookup_field = lookup_field
        self.option_type = option_type
        self.edit = edit

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        queryset = self.queryset.order_by(self.lookup_field)
        context["widget"]["queryset_options"] = queryset
        context["widget"]["options_json"] = json.dumps(
            [getattr(obj, self.lookup_field) for obj in queryset.all()]
        )
        context["widget"]["value"] = (
            json.dumps(
                [
                    getattr(queryset.get(id=v), self.lookup_field) if isinstance(v, int) else v
                    for v in value
                ]
            )
            if value is not None
            else "[]"
        )
        context["widget"]["option_type"] = self.option_type
        context["widget"]["edit"] = self.edit
        return context

    # https://docs.djangoproject.com/en/6.0/ref/forms/widgets/#django.forms.Widget.value_from_datadict
    def value_from_datadict(self, data, files, name):
        value = dict(data).get(name)
        if value is None:
            return None
        # Translate between ManyRelatedManager and select element value
        if isinstance(value, list):
            return self.queryset.filter(**{(self.lookup_field + "__in"): value})
        return value.all()
