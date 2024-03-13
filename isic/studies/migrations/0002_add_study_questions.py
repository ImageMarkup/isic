# Generated by Django 3.1.4 on 2020-12-16 19:32
from __future__ import annotations

from django.db import migrations


def add_questions(apps, schema_editor):
    YES_NO_CHOICES = ["Yes", "No"]

    Question = apps.get_model("studies", "Question")
    QuestionChoice = apps.get_model("studies", "QuestionChoice")

    questions = {
        "Can this be used for the desired application/study?": YES_NO_CHOICES,
        "Does the lesion appear to be benign or malignant?": [
            "Benign",
            "Malignant",
        ],
        "Does the lesion appear to be benign, malignant, or neither?": [
            "Benign",
            "Malignant",
            "Unsure",
        ],
        "Does the lesion appear with border/corners?": YES_NO_CHOICES,
        "Does the lesion contain a network?": YES_NO_CHOICES,
        "Does the lesion image contain a ruler?": YES_NO_CHOICES,
        "Does the lesion image contain any sensitive content or potential Protected Health Information?": YES_NO_CHOICES,  # noqa: E501
        "Does the lesion image contain light leak spots?": YES_NO_CHOICES,
        "Does the lesion image contain pen markings?": YES_NO_CHOICES,
        "Indicate your management decision": ["Biopsy", "Observation and/or reassurance"],
        "Is the lesion area blurry?": YES_NO_CHOICES,
        "Is the lesion diagnosis consistent with the current image?": YES_NO_CHOICES,
        "Is the lesion a nevus, seborrheic keratosis, or melanoma?": [
            "Nevus",
            "Seborrheic keratosis",
            "Melanoma",
        ],
        "Is the lesion a nevus, melanoma, or other?": ["Melanoma", "Nevus", "Other"],
        "Is the lesion organized or disorganized?": ["Organized", "Disorganized"],
        "Is there hair obscuring the lesion?": YES_NO_CHOICES,
        "What is your level of confidence (1-7)?": [
            "Absolutely confident",
            "Confident",
            "Somewhat confident",
            "Neither confident nor unconfident",
            "Somewhat unconfident",
            "Unconfident",
            "Not confident at all",
        ],
        "What is your level of confidence (1-5)?": [
            "Very Confident",
            "Somewhat Confident",
            "Neither Confident / Not Confident",
            "Somewhat Not Confident",
            "Very Not Confident",
        ],
        "Does the lesion contain the color black?": YES_NO_CHOICES,
        "Does the lesion contain the color brown?": YES_NO_CHOICES,
        "Does the lesion contain the color grey/blue?": YES_NO_CHOICES,
        "Does the lesion contain the color light brown?": YES_NO_CHOICES,
        "Does the lesion contain the color red?": YES_NO_CHOICES,
        "Does the lesion contain the color white?": YES_NO_CHOICES,
    }

    for question, choices in questions.items():
        q = Question.objects.create(prompt=question, official=True)

        for choice in choices:
            QuestionChoice.objects.create(question=q, text=choice)


class Migration(migrations.Migration):
    dependencies = [
        ("studies", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_questions),
    ]
