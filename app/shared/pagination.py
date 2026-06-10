from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


def get_offset_limit(params: PaginationParams) -> tuple[int, int]:
    offset = (params.page - 1) * params.page_size
    return offset, params.page_size

