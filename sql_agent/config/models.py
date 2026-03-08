from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool
    description: str
    relationships: str | None = None


class TableSchema(BaseModel):
    name: str
    description: str = ""
    columns: list[ColumnInfo]

    def to_text(self) -> str:
        """
        Render table schema as a plain-text string for embedding and LLM prompts.
        """
        lines = [f"Table: {self.name}"]
        if self.description:
            lines.append(f"Description: {self.description}")
        for col in self.columns:
            null_label = "NULL" if col.nullable else "NOT NULL"
            rel = f" | {col.relationships}" if col.relationships else ""
            lines.append(
                f"  - {col.name} ({col.data_type}, {null_label}): {col.description}{rel}"
            )
        return "\n".join(lines)


# --- /index ---

class IndexResponse(BaseModel):
    status: str
    tables_indexed: int
    latency_ms: float


# --- /retrieve ---

class RetrievedTable(BaseModel):
    name: str
    score: float = Field(..., description="Cosine similarity score in [0, 1].")
    columns: list[str]


class RetrieveResponse(BaseModel):
    question: str
    tables: list[RetrievedTable]
    top_k: int
    retrieval_latency_ms: float


# --- /query (stub, filled in later) ---

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class QueryResponse(BaseModel):
    sql: str
    attempts: int
    tables_used: list[str]
    latency_ms: float

