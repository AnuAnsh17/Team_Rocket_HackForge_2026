"""Shared DTO primitives: money, field evidence, errors and pagination.

Money handling is the detail that matters most here. Values are ``Decimal`` end
to end and serialise to JSON as decimal strings, never floats, because binary
floating point cannot represent 0.10 exactly and an expense auditor must not
lose paise to representation error.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    field_validator,
)

from app.core.enums import FieldSource, FindingResult, FindingSeverity

# ISO 4217 currency code, uppercased.
CurrencyCode = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]

# A monetary value as a decimal string.
#
# The annotations do three separate jobs, and all three are load-bearing:
#
#   PlainSerializer   serialises Decimal to a plain decimal string, never an
#                     exponent form and never a JSON float.
#   WithJsonSchema    forces the generated schema to say "string". Without this,
#                     Pydantic emits {"type": "number"} alongside it for Decimal,
#                     and the generated TypeScript client would type every amount
#                     as `number | string | null`. A client would then do float
#                     arithmetic and silently lose paise before the value ever
#                     reached the API.
#   the validator in Money  refuses a JSON number outright, so a caller that sends
#                     1400.0 gets a clear validation error instead of a value that
#                     differs in the last decimal place.
MoneyString = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value, "f"), return_type=str),
    WithJsonSchema({"type": "string", "examples": ["1400.00"]}),
]


class ApiModel(BaseModel):
    """Base for every response model."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ErrorDetail(BaseModel):
    """Structured, machine-readable error detail. Never contains a stack trace."""

    model_config = ConfigDict(extra="allow")
    field: str | None = None
    value: str | None = None


class FieldErrorDetail(BaseModel):
    """Validation detail for one request field."""

    location: list[str] = Field(default_factory=list)
    message: str
    type: str


class ErrorEnvelope(ApiModel):
    """The single error response shape."""

    class ErrorBody(BaseModel):
        code: str = Field(..., description="Stable machine-readable error code.")
        message: str = Field(..., description="Human-readable explanation, safe to display.")
        details: list[dict[str, object]] = Field(default_factory=list)
        request_id: str = Field(..., description="Correlation id for support and log lookup.")

    error: ErrorBody


class SourceReference(ApiModel):
    """Where a finding's rule came from. Required on any rule-backed finding."""

    document_id: str | None = Field(
        default=None, description="Identifier of the policy document the rule was derived from."
    )
    clause: str | None = Field(
        default=None, description="Section/clause reference, for example 2.3."
    )
    text_excerpt: str | None = Field(
        default=None, description="Verified excerpt of the clause. Never paraphrased from memory."
    )


class EvidenceLocation(ApiModel):
    """Optional receipt region supporting a value.

    Present only when the extraction provider actually reported a region.
    Coordinates are never fabricated: an absent region is ``null``.
    """

    receipt_id: uuid.UUID | None = None
    page: int | None = Field(default=None, ge=1)
    region: list[float] | None = Field(
        default=None,
        description="Normalised [x, y, width, height] within the page, when supplied.",
    )


class FieldValue[T](ApiModel):
    """A single expense field together with its provenance.

    A field can hold a value and still be uncertain. Provenance therefore travels
    with the value instead of being inferred, and an employee-entered value can
    never be presented as receipt evidence.
    """

    value: T | None = None
    source: FieldSource
    reviewed: bool = False
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Provider quality signal, NOT a calibrated probability. Null whenever the "
            "provider supplies no meaningful value rather than being invented."
        ),
    )
    evidence: EvidenceLocation | None = None
    uncertainty_reason: str | None = None


class Money(ApiModel):
    """The canonical monetary field.

    Approved contract decision: ``amount`` uses this one structure everywhere,
    including provenance, so that a reviewer can always see whether a total came
    from a receipt or from the employee.
    """

    value: MoneyString | None = Field(default=None, description="Decimal amount as a JSON string.")
    currency: CurrencyCode | None = None
    source: FieldSource
    reviewed: bool = False
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: EvidenceLocation | None = None
    uncertainty_reason: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _reject_json_number(cls, value: Any) -> Any:
        """Refuse a JSON number for an amount.

        Binary floating point cannot represent most currency amounts exactly, so a
        client that sends 0.1 has already lost information before the request
        arrives. Rejecting it turns a silent rounding bug into a clear error.
        """
        if isinstance(value, float):
            raise ValueError(
                'Send monetary values as a decimal string such as "1400.00", not as a '
                "JSON number: binary floating point cannot represent most currency amounts "
                "exactly."
            )
        return value


class NonNegativeMoney(ApiModel):
    """A monetary amount with no exchange-rate provenance.

    Used for derived/computed values such as a converted reporting amount, where
    the rate trio below records how the number was produced.
    """

    value: MoneyString | None = None
    currency: CurrencyCode | None = None
    rate: MoneyString | None = Field(
        default=None, description="Applied rate, when a conversion occurred."
    )
    rate_date: date | None = None
    rate_source: str | None = Field(default=None, description="Documented source of the rate.")


class PageInfo(ApiModel):
    """Pagination metadata."""

    limit: int = Field(..., ge=1)
    next_cursor: str | None = Field(
        default=None, description="Opaque cursor for the next page. Null on the final page."
    )
    total: int | None = Field(
        default=None,
        description="Total matching rows, or null when the count is intentionally omitted.",
    )


class Page[T](ApiModel):
    """The list envelope used by every list endpoint."""

    items: list[T]
    page: PageInfo


class TriStateSummary(ApiModel):
    """Counts of findings by tri-state result, for queue and KPI surfaces."""

    pass_count: int = Field(0, alias="pass")
    fail_count: int = Field(0, alias="fail")
    unknown_count: int = Field(0, alias="unknown")

    model_config = ConfigDict(populate_by_name=True)


class FindingCounts(ApiModel):
    result: FindingResult
    severity: FindingSeverity
    count: int = Field(..., ge=0)
