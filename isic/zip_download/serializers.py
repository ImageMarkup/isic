from rest_framework import serializers


class ZipFileEntrySerializer(serializers.Serializer):
    url = serializers.URLField()
    zipPath = serializers.CharField()  # noqa: N815


# modeling https://github.com/scosman/zipstreamer#json-descriptor-a
class ZipFileDescriptorSerializer(serializers.Serializer):
    suggestedFilename = serializers.CharField()  # noqa: N815
    files = ZipFileEntrySerializer(many=True)
