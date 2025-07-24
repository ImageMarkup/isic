import datetime
import random
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
        skip_postgeneration_save = True

    prompt = factory.Faker("sentence")
    official = factory.Faker("boolean")
    # Make all questions a selection, since we're making choices
    # TODO: Support other question types
    type = Question.QuestionType.SELECT

    choices = factory.RelatedFactoryList(
        "isic.studies.tests.factories.QuestionChoiceFactory",
        factory_related_name="question",
        size=lambda: random.randint(1, 5),
    )


class QuestionChoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QuestionChoice

    question = factory.SubFactory(QuestionFactory, choices=[])
    text = factory.Faker("sentence")


class FeatureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Feature

    required = factory.Faker("boolean")
    name = factory.Faker("words")
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
        if not create:
            return
        if extracted:
            # A list of features were passed in, use them
            self.features.add(*extracted)

    @factory.post_generation
    def questions(self, create, extracted, *, required: bool = False, **kwargs):
        if not create:
            return
        if extracted:
            # A list of questions were passed in, use them
            # TODO: the required status should be settable per question
            self.questions.add(*extracted, through_defaults={"required": required})


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

    study = factory.SubFactory(StudyFactory)
    image = factory.SubFactory(ImageFactory)
    annotator = factory.SubFactory(UserFactory)

    task = factory.SubFactory(
        StudyTaskFactory,
        study=factory.SelfAttribute("..study"),
        image=factory.SelfAttribute("..image"),
        annotator=factory.SelfAttribute("..annotator"),
    )

    start_time = factory.Faker("date_time", tzinfo=datetime.UTC)


class ResponseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Response

    annotation = factory.SubFactory(
        AnnotationFactory,
        study__questions=factory.List([factory.SelfAttribute(".....question")]),
    )
    question = factory.SubFactory(QuestionFactory)
    choice = factory.LazyAttribute(lambda o: random.choice(o.question.choices.all()))
    # QuestionFactory always generate choice questions, so the response has no "value"
    value = None


class MarkupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Markup

    annotation = factory.SubFactory(
        AnnotationFactory,
        study__features=factory.List([factory.SelfAttribute(".....feature")]),
    )
    feature = factory.SubFactory(FeatureFactory)
    present = factory.Faker("boolean")
