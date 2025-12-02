"""Pydantic models for the metadata API responses."""

from pydantic import BaseModel, ConfigDict, Field


class Resource(BaseModel):
    """Metadata resource; keep permissive."""

    model_config = ConfigDict(extra="allow")
    id: str = Field(..., description="Unique identifier for the resource", examples=["attasidor"])
    type: str = Field(
        ..., description="Type of the resource", examples=["corpus", "lexicon", "model", "analysis", "utility"]
    )
    name: dict[str, str] | None = Field(
        None,
        description="Name of the resource in multiple languages",
        examples=[{"sv": "8 SIDOR", "en": "8 SIDOR"}],
    )
    short_description: dict[str, str] | None = Field(
        None,
        description="Short description of the resource in multiple languages",
        examples=[{"sv": "Nyhetsartiklar från 8 SIDOR.", "en": "News articles from 8 SIDOR."}],
    )


class AllResouresList(BaseModel):
    """List of all metadata resources, grouped by resource type."""

    corpus: list[Resource] = Field(..., description="List of corpus resources")
    lexicon: list[Resource] = Field(..., description="List of lexicon resources")
    model: list[Resource] = Field(..., description="List of model resources")
    analysis: list[Resource] = Field(..., description="List of analysis resources")
    utility: list[Resource] = Field(..., description="List of utility resources")


class ResourceList(BaseModel):
    """List of metadata resources."""

    resource_type: str = Field(
        ..., description="Type of the resources", examples=["corpus", "lexicon", "model", "analysis", "utility"]
    )
    hits: int = Field(..., description="Number of resources in the list", examples=[42])
    resources: list[Resource]


class CollectionsList(BaseModel):
    """List of resource collections."""

    hits: int = Field(..., description="Number of collections in the list", examples=[5])
    resources: list[Resource]


class BibtexResponse(BaseModel):
    """Response model for BibTeX entries."""

    bibtex: str = Field(
        ...,
        description="BibTeX citation as text",
        examples=[
            """@misc{attasidor,\n  doi = {10.23695/f6ds-f045},\n  url = {https://spraakbanken.gu.se/resurser/attasidor},
            \n  author = {Språkbanken Text},\n  keywords = {Language Technology (Computational Linguistics)},
            \n  language = {swe},\n  title = {8 Sidor},\n  publisher = {Språkbanken Text},\n  year = {2024}\n}"""
        ],
    )


class RenewCacheResponse(BaseModel):
    """Response model for cache renewal requests."""

    task_id: str = Field(
        ..., description="ID of the cache renewal task", examples=["c09e5583-dd05-4949-9734-e02b60fad42a"]
    )
    message: str = Field(
        ...,
        description="Message indicating the status of the cache renewal request",
        examples=["Cache renewal triggered in background."],
    )


class IdAvailabilityResponse(BaseModel):
    """Response model for resource ID availability check."""

    id: str = Field(..., description="The resource ID that was checked", examples=["my-new-resource"])
    available: bool = Field(
        ...,
        description="Indicates whether the resource ID is available",
        examples=[True, False],
    )
