from django import forms
import pydantic_core
from pyparsing.exceptions import ParseException

from isic.core.models.image import Image
from isic.core.serializers import SearchQueryIn


class ImageSearchForm(forms.Form):
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "diagnosis:melanoma OR diagnosis:nevus"}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        collections = kwargs.pop("collections")
        super().__init__(*args, **kwargs)
        self.fields["collections"] = forms.ModelMultipleChoiceField(
            queryset=collections, required=False
        )

    def clean(self):
        # This is a little bit ugly but it allows us to keep putting the repeated logic of finding
        # images from a search query in a single place. Unfortunately the input to collections is a
        # comma delimited string - so build one even though we already have the collection objects.
        if "collections" in self.cleaned_data:
            collections = ",".join(
                map(str, self.cleaned_data["collections"].values_list("pk", flat=True))
            )
        else:
            # handle the case of a malformed input to the collections field
            collections = ""

        serializer_input = {
            **self.cleaned_data,
            "collections": collections,
        }
        try:
            serializer = SearchQueryIn(**serializer_input)
        except pydantic_core.ValidationError as exc:
            raise forms.ValidationError([e["msg"] for e in exc.errors()]) from exc

        try:
            self.results = serializer.to_queryset(
                self.user, Image.objects.select_related("accession")
            )
        except ParseException as e:
            raise forms.ValidationError("Invalid search query.") from e

        return super().clean()
