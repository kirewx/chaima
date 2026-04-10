from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Wrapper for paginated list responses.

    Parameters
    ----------
    items : list[T]
        The page of results.
    total : int
        Total number of matching records.
    offset : int
        Offset used for this page.
    limit : int
        Limit used for this page.
    """

    items: list[T]
    total: int
    offset: int
    limit: int
