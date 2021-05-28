from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db import models
import numpy as np
import pandas as pd
from s3_file_field import S3FileField

from isic.core.models import CreationSortedTimeStampedModel

from .cohort import Cohort


class MetadataFile(CreationSortedTimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='metadata_files')

    blob = S3FileField(validators=[FileExtensionValidator(allowed_extensions=['csv'])])
    blob_name = models.CharField(max_length=255, editable=False)
    blob_size = models.PositiveBigIntegerField(editable=False)

    def __str__(self) -> str:
        return self.blob_name

    def to_df(self):
        with self.blob.open() as csv:
            df = pd.read_csv(csv, header=0)

        # pydantic expects None for the absence of a value, not NaN
        df = df.replace({np.nan: None})

        return df