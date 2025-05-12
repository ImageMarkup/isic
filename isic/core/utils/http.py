# StreamingHttpResponse requires a File-like class that has a 'write' method
class Buffer:
    def write(self, value: str) -> bytes:
        return value.encode("utf-8")
