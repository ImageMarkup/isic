from rest_framework import serializers


class ZipFileFileDescriptorSerializer(serializers.Serializer):
    url = serializers.URLField()
    zipPath = serializers.CharField()  # noqa: N815


# modeling https://github.com/scosman/zipstreamer#json-descriptor-a
class ZipFileDescriptorSerializer(serializers.Serializer):
    suggestedFilename = serializers.CharField()  # noqa: N815
    files = ZipFileFileDescriptorSerializer(many=True)
