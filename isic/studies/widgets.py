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
