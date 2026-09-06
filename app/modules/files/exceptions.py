"""Domain exceptions for the `files` module."""


class StoredFileNotFoundError(Exception):
    """Raised when a `File` with the given id does not exist.

    Named `StoredFileNotFoundError` rather than `FileNotFoundError` to
    avoid shadowing the Python builtin of the same name (raised by
    `open()` and friends) — accidentally catching or confusing the two
    would be an easy, hard-to-notice bug.
    """

    def __init__(self, file_id: int) -> None:
        self.file_id = file_id
        super().__init__(f"File {file_id} not found")
