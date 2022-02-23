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

    prompt = factory.Faker('sentence')
    type = factory.Faker('random_element', elements=[e[0] for e in Question.QuestionType.choices])
    official = factory.Faker('boolean')


class QuestionChoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QuestionChoice

    question = factory.SubFactory(QuestionFactory)
    text = factory.Faker('sentence')


class FeatureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Feature

    required = factory.Faker('boolean')
    name = factory.Faker('words')
    official = factory.Faker('boolean')


class StudyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Study

    creator = factory.SubFactory(UserFactory)

    name = factory.Faker('text', max_nb_chars=100)
    description = factory.Faker('sentences')
    collection = factory.SubFactory(CollectionFactory)

    public = factory.Faker('boolean')

    @factory.post_generation
    def owners(self, create, extracted, **kwargs):
        owners = [self.creator] if extracted is None else extracted
        for owner in owners:
            self.owners.add(owner)

    @factory.post_generation
    def features(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of features were passed in, use them
            for feature in extracted:
                self.features.add(feature)

    @factory.post_generation
    def questions(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of questions were passed in, use them
            for question in extracted:
                self.questions.add(question)


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

    study = factory.SelfAttribute('task.study')
    image = factory.SelfAttribute('task.image')
    task = factory.SubFactory(StudyTaskFactory)
    annotator = factory.SelfAttribute('task.annotator')
    start_time = factory.Faker('date_time', tzinfo=factory.Faker('pytimezone'))


class ResponseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Response

    annotation = factory.SubFactory(AnnotationFactory)
    question = factory.SubFactory(QuestionFactory)
    choice = factory.SubFactory(QuestionChoiceFactory)


class MarkupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Markup

    annotation = factory.SubFactory(AnnotationFactory)
    feature = factory.SubFactory(FeatureFactory)
    present = factory.Faker('boolean')
