from pytest_factoryboy import register

from .factories import (
    AnnotationFactory,
    FeatureFactory,
    MarkupFactory,
    QuestionChoiceFactory,
    QuestionFactory,
    ResponseFactory,
    StudyFactory,
    StudyTaskFactory,
)

register(QuestionFactory, 'question')
register(QuestionChoiceFactory, 'questionchoice')
register(FeatureFactory, 'feature')
register(StudyFactory, 'study')
register(StudyTaskFactory, 'studytask')
register(AnnotationFactory, 'annotation')
register(ResponseFactory, 'response')
register(MarkupFactory, 'markup')
