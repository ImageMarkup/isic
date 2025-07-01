from typing import Any

import factory
import factory.django

from isic.core.tests.factories import CollectionFactory, ImageFactory
from isic.factories import UserFactory
from isic.studies.models import (
    Annotation,
    Feature,
    Markup,
    Question,
    QuestionChoice,
    Response,
    Study,
    StudyTask,
)


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Question

    prompt = factory.Faker("sentence")
    type = factory.Faker("random_element", elements=[e[0] for e in Question.QuestionType.choices])
    official = factory.Faker("boolean")


class QuestionChoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QuestionChoice

    question = factory.SubFactory(QuestionFactory)
    text = factory.Faker("sentence")


class FeatureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Feature

    required = factory.Faker("boolean")
    name = factory.Faker("sentence")
    official = factory.Faker("boolean")


class StudyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Study
        skip_postgeneration_save = True

    creator = factory.SubFactory(UserFactory)

    name = factory.Faker("text", max_nb_chars=100)
    description = factory.Faker("sentences")
    collection = factory.SubFactory(CollectionFactory)

    public = factory.Faker("boolean")

    @factory.post_generation
    def owners(self, create: bool, extracted: Any, **kwargs: Any) -> None:  # noqa: FBT001
        if not create:
            return
        if extracted is None:
            # The creator is the default owner.
            extracted = [self.creator]
        self.owners.add(*extracted)

    @factory.post_generation
    def features(self, create: bool, extracted: Any, **kwargs: Any) -> None:  # noqa: FBT001
        if not create or not extracted:
            return
        self.features.add(*extracted)

    @factory.post_generation
    def questions(self, create: bool, extracted: Any, **kwargs: Any) -> None:  # noqa: FBT001
        if not create or not extracted:
            return
        self.questions.add(*extracted)


class StudyTaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StudyTask

    study = factory.SubFactory(StudyFactory)
    # TODO: annotators might become M2M in the future
    annotator = factory.SubFactory(UserFactory)
    image = factory.SubFactory(ImageFactory)


class AnnotationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Annotation

    study = factory.SelfAttribute("task.study")
    image = factory.SelfAttribute("task.image")
    task = factory.SubFactory(StudyTaskFactory)
    annotator = factory.SelfAttribute("task.annotator")
    start_time = factory.Faker("date_time", tzinfo=factory.Faker("pytimezone"))


class ResponseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Response

    annotation = factory.SubFactory(AnnotationFactory)
    question = factory.SubFactory(QuestionFactory)
    choice = factory.SubFactory(QuestionChoiceFactory)
    value = factory.Faker("pyint")


class MarkupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Markup

    annotation = factory.SubFactory(AnnotationFactory)
    feature = factory.SubFactory(FeatureFactory)
    present = factory.Faker("boolean")
