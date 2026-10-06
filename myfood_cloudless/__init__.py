"""myfood-cloudless: local, credential-free reader for myfood greenhouses."""
__all__ = ["Reader"]
__version__ = "0.1.0"


def __getattr__(name):
    if name == "Reader":
        from .reader import Reader
        return Reader
    raise AttributeError(name)
