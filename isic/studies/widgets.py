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
