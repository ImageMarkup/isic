from __future__ import annotations

from enum import Enum
import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, root_validator, validator
from pydantic.types import constr


class BaseStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value: str):
        raise NotImplementedError


class ClinicalSize(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[float]:
        if not value:
            return None

        match = re.match('(.+)(um|mm|cm)$', value)

        if not match:
            raise ValueError(f'Invalid clinical size of {value}.')

        float_value, units = match.groups()
        float_value = float(float_value)

        # Convert to mm
        if units == 'um':
            float_value *= 1e-3
        elif units == 'cm':
            float_value *= 1e1

        return float_value


class Age(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[int]:
        if not value:
            return None
        elif value == '85+':
            value = 85

        value: int = int(value)
        # clip to 85
        value = min(value, 85)
        return value


class Sex(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if not value:
            return None

        if value == 'm':
            value = 'male'
        elif value == 'f':
            value = 'female'

        if value not in ['male', 'female']:
            raise ValueError(f'Invalid sex of: {value}.')

        return value


class BenignMalignantEnum(str, Enum):
    benign = 'benign'
    malignant = 'malignant'
    indeterminate = 'indeterminate'
    indeterminate_benign = 'indeterminate/benign'
    indeterminate_malignant = 'indeterminate/malignant'


# todo indeterminable
class BenignMalignant(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if not value:
            return None

        if value not in BenignMalignantEnum._value2member_map_:
            raise ValueError(f'Invalid benign/malignant value of {value}.')

        return value


class DiagnosisConfirmTypeEnum(str, Enum):
    histopathology = 'histopathology'
    serial_imaging_showing_no_change = 'serial imaging showing no change'
    single_image_expert_consensus = 'single image expert consensus'
    confocal_microscopy_with_consensus_dermoscopy = 'confocal microscopy with consensus dermoscopy'


class DiagnosisConfirmType(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in DiagnosisConfirmTypeEnum._value2member_map_:
            raise ValueError(f'Invalid diagnosis confirm type of: {value}.')
        return value


class DiagnosisEnum(str, Enum):
    actinic_keratosis = 'actinic keratosis'
    adnexal_tumor = 'adnexal tumor'
    aimp = 'AIMP'
    angiokeratoma = 'angiokeratoma'
    angioma = 'angioma'
    basal_cell_carcinoma = 'basal cell carcinoma'
    cafe_au_lait_macule = 'cafe-au-lait macule'
    dermatofibroma = 'dermatofibroma'
    ephelis = 'ephelis'
    lentigo_nos = 'lentigo NOS'
    lentigo_simplex = 'lentigo simplex'
    lichenoid_keratosis = 'lichenoid keratosis'
    melanoma = 'melanoma'
    melanoma_metastasis = 'melanoma metastasis'
    merkel_cell_carcinoma = 'merkel cell carcinoma'
    mucosal_melanosis = 'mucosal melanosis'
    nevus = 'nevus'
    nevus_spilus = 'nevus spilus'
    seborrheic_keratosis = 'seborrheic keratosis'
    solar_lentigo = 'solar lentigo'
    squamous_cell_carcinoma = 'squamous cell carcinoma'
    clear_cell_acanthoma = 'clear cell acanthoma'
    atypical_spitz_tumor = 'atypical spitz tumor'
    acrochordon = 'acrochordon'
    angiofibroma_or_fibrous_papule = 'angiofibroma or fibrous papule'
    neurofibroma = 'neurofibroma'
    pyogenic_granuloma = 'pyogenic granuloma'
    scar = 'scar'
    sebaceous_adenoma = 'sebaceous adenoma'
    sebaceous_hyperplasia = 'sebaceous hyperplasia'
    verruca = 'verruca'
    atypical_melanocytic_proliferation = 'atypical melanocytic proliferation'
    epidermal_nevus = 'epidermal nevus'
    pigmented_benign_keratosis = 'pigmented benign keratosis'
    vascular_lesion = 'vascular lesion'
    other = 'other'


class Diagnosis(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in DiagnosisEnum._value2member_map_:
            raise ValueError(f'Invalid diagnosis of: {value}.')
        return value


class NevusTypeEnum(str, Enum):
    blue = 'blue'
    combined = 'combined'
    nevus_nos = 'nevus NOS'
    deep_penetrating = 'deep penetrating'
    halo = 'halo'
    persistent_recurrent = 'persistent/recurrent'
    pigmented_spindle_cell_of_reed = 'pigmented spindle cell of reed'
    plexiform_spindle_cell = 'plexiform spindle cell'
    special_site = 'special site'
    spitz = 'spitz'


class NevusType(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in NevusTypeEnum._value2member_map_:
            raise ValueError(f'Invalid nevus type of: {value}.')
        return value


class ImageTypeEnum(str, Enum):
    dermoscopic = 'dermoscopic'
    clinical = 'clinical'
    overview = 'overview'


class ImageType(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in ImageTypeEnum._value2member_map_:
            raise ValueError(f'Invalid image type of: {value}.')
        return value


class DermoscopicTypeEnum(str, Enum):
    contact_polarized = 'contact polarized'
    contact_non_polarized = 'contact non-polarized'
    non_contact_polarized = 'non-contact polarized'


class DermoscopicType(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in DermoscopicTypeEnum._value2member_map_:
            raise ValueError(f'Invalid dermoscopic type of: {value}.')
        return value


class MelTypeEnum(str, Enum):
    superficial_spreading_melanoma = 'superficial spreading melanoma'
    nodular_melanoma = 'nodular melanoma'
    lentigo_maligna_melanoma = 'lentigo maligna melanoma'
    acral_lentiginous_melanoma = 'acral lentiginous melanoma'
    melanoma_nos = 'melanoma NOS'


class MelType(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in MelTypeEnum._value2member_map_:
            raise ValueError(f'Invalid mel type of: {value}.')
        return value


class MelClassEnum(str, Enum):
    melanoma_in_situ = 'melanoma in situ'
    invasive_melanoma = 'invasive melanoma'
    recurrent_persistent_melanoma_in_situ = 'recurrent/persistent melanoma, in situ'
    recurrent_persistent_melanoma_invasive = 'recurrent/persistent melanoma, invasive'
    melanoma_nos = 'melanoma NOS'


class MelClass(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in MelClassEnum._value2member_map_:
            raise ValueError(f'Invalid mel class of: {value}.')
        return value


class MelThickMm(BaseStr):
    _regex = re.compile(
        r"""
        (.+?)    # Non-greedy
        (?:mm)?  # Optional units, non-capturing
        $
        """,
        re.VERBOSE,
    )

    @classmethod
    def validate(cls, value: str) -> Optional[float]:
        # Parse value into floating point component and units
        result = re.match(cls._regex, value)
        if not result:
            raise ValueError(f'Invalid melanoma thickness of: {value}.')

        value = result.group(1)
        int_value = float(value)

        return int_value


class MelMitoticIndexEnum(str, Enum):
    zero = '0/mm^2'
    lt_one = '<1/mm^2'
    one = '1/mm^2'
    two = '2/mm^2'
    three = '3/mm^2'
    four = '4/mm^2'
    gt_4 = '>4/mm^2'


class MelMitoticIndex(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in GeneralAnatomicSiteEnum._value2member_map_:
            raise ValueError(f'Invalid mel mitotic index of: {value}.')
        return value


class GeneralAnatomicSiteEnum(str, Enum):
    head_neck = 'head/neck'
    upper_extremity = 'upper extremity'
    lower_extremity = 'lower extremity'
    anterior_torso = 'anterior torso'
    posterior_torso = 'posterior torso'
    palms_soles = 'palms/soles'
    lateral_torso = 'lateral torso'
    oral_genital = 'oral/genital'


class GeneralAnatomicSite(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in GeneralAnatomicSiteEnum._value2member_map_:
            raise ValueError(f'Invalid general anatomical site of: {value}.')
        return value


class ColorTintEnum(str, Enum):
    blue = 'blue'
    pink = 'pink'
    none = 'none'


class ColorTint(BaseStr):
    @classmethod
    def validate(cls, value: str) -> Optional[str]:
        if value not in ColorTintEnum._value2member_map_:
            raise ValueError(f'Invalid color tint of: {value}.')
        return value


PatientIdType = constr(regex=r'^IP_[0-9]{7}$')
LesionIdType = constr(regex=r'^IL_[0-9]{7}$')


# TODO: exif_* headers
class MetadataRow(BaseModel):
    age: Optional[Age]
    sex: Optional[Sex]
    benign_malignant: Optional[BenignMalignant]
    diagnosis: Optional[Diagnosis]
    diagnosis_confirm_type: Optional[DiagnosisConfirmType]
    personal_hx_mm: Optional[bool]
    family_hx_mm: Optional[bool]
    clin_size_long_diam_mm: Optional[ClinicalSize]
    melanocytic: Optional[bool]
    patient_id: PatientIdType = None
    lesion_id: LesionIdType = None
    acquisition_day: Optional[int]  # TODO: metadata dictionary
    marker_pen: Optional[bool]
    hairy: Optional[bool]
    blurry: Optional[bool]
    nevus_type: Optional[NevusType]
    image_type: Optional[ImageType]
    dermoscopic_type: Optional[DermoscopicType]
    anatom_site_general: Optional[GeneralAnatomicSite]
    color_tint: Optional[ColorTint]
    mel_class: Optional[MelClass]
    mel_mitotic_index: Optional[ColorTint]
    mel_thick_mm: Optional[MelThickMm]
    mel_type: Optional[MelType]
    mel_ulcer: Optional[bool]

    unstructured: Dict[str, Any]

    # See https://github.com/samuelcolvin/pydantic/issues/2285 for more detail
    @root_validator(pre=True)
    def build_extra(cls, values: Dict[str, Any]) -> Dict[str, Any]:  # noqa: N805
        all_required_field_names = {
            field.alias for field in cls.__fields__.values() if field.alias != 'unstructured'
        }  # to support alias

        unstructured: Dict[str, Any] = {}
        for field_name in list(values):
            if field_name not in all_required_field_names:
                unstructured[field_name] = values.pop(field_name)
        values['unstructured'] = unstructured
        return values

    @validator('*', pre=True)
    @classmethod
    def strip(cls, v):
        if isinstance(v, str):
            v = v.strip()
        return v

    @validator(
        'anatom_site_general',
        'benign_malignant',
        'clin_size_long_diam_mm',
        'diagnosis_confirm_type',
        'mel_mitotic_index',
        'mel_thick_mm',
        'sex',
        pre=True,
    )
    @classmethod
    def lower(cls, v):
        if isinstance(v, str):
            v = v.lower()
        return v

    @validator('diagnosis')
    @classmethod
    def validate_no_benign_melanoma(cls, v, values):
        if 'benign_malignant' in values:

            if v == 'melanoma' and values['benign_malignant'] == 'benign':
                raise ValueError('A benign melanoma cannot exist.')

            if v == 'nevus' and values['benign_malignant'] not in [
                BenignMalignantEnum.benign,
                BenignMalignantEnum.indeterminate_benign,
                BenignMalignantEnum.indeterminate,
            ]:
                raise ValueError(f'A {values["benign_malignant"]} nevus cannot exist.')

        return v

    @validator('nevus_type')
    @classmethod
    def validate_non_nevus_diagnoses(cls, v, values):
        if (
            v
            and values.get('diagnosis')
            and values['diagnosis'] not in [DiagnosisEnum.nevus, DiagnosisEnum.nevus_spilus]
        ):
            raise ValueError(f'Nevus type is inconsistent with {values["diagnosis"]}.')
        return v

    @validator('mel_class', 'mel_mitotic_index', 'mel_thick_mm', 'mel_type', 'mel_ulcer')
    @classmethod
    def validate_melanoma_fields(cls, v, values, config, field):
        if v and 'diagnosis' in values and values['diagnosis'] != 'melanoma':
            raise ValueError(f'A non-melanoma {field} cannot exist.')
        return v

    @validator('diagnosis_confirm_type')
    @classmethod
    def validate_non_histopathology_diagnoses(cls, v, values):
        if 'benign_malignant' in values:
            if v != 'histopathology' and values['benign_malignant'] in [
                BenignMalignantEnum.malignant,
                BenignMalignantEnum.indeterminate_benign,
                BenignMalignantEnum.indeterminate_malignant,
                BenignMalignantEnum.indeterminate,
            ]:

                raise ValueError(f'A {values["benign_malignant"]} ...')

        return v

    @validator('dermoscopic_type')
    @classmethod
    def validate_dermoscopic_fields(cls, v, values):
        if values.get('image_type') == ImageTypeEnum.dermoscopic and v:
            raise ValueError(
                f'Image type {values["image_type"]} inconsistent with dermoscopic type {v}.'
            )
