from django import template

register = template.Library()


@register.filter
def to_js(value):
    return {
        'id': value.id,
        'quality_check': value.quality_check,
        'diagnosis_check': value.diagnosis_check,
        'phi_check': value.phi_check,
        'duplicate_check': value.duplicate_check,
        'lesion_check': value.lesion_check,
    }
