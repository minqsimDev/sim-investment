from abc import ABC


class BaseProvider(ABC):
    """Marker base class for data providers.
    Swap implementations by replacing the provider in fetcher.py — no other changes needed.
    """
    pass
