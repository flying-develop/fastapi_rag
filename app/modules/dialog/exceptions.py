"""Domain exceptions for the `dialog` module."""


class DialogNotFoundError(Exception):
    """Raised when a `Dialog` with the given id does not exist."""

    def __init__(self, dialog_id: int) -> None:
        self.dialog_id = dialog_id
        super().__init__(f"Dialog {dialog_id} not found")
