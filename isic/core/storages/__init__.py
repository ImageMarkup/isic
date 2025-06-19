class PreventRenamingMixin:
    """
    Mixin to prevent renaming of files in storage.

    This is useful for preventing underlying storages from writing files to alternative locations
    when the file already exists.
    """

    def get_alternative_name(self, file_root, file_ext):
        raise Exception(f"{file_root}{file_ext} already exists.")
