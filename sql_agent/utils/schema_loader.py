import pandas as pd

from sql_agent.config.models import ColumnInfo, TableSchema

# The table description has: table info + how and where to use this table.
# more info -> more better is more udnerstanidng to the model.

_TABLE_DESCRIPTIONS: dict[str, str] = {
    "customers_tbl": (
        "Stores customer account information including name, email, tier (standard, premium, enterprise), and region. "
        "Use this table to filter or group by customer segment, identify high-value customers, or join with tickets."
    ),
    "agents_tbl": (
        "Stores support agent profiles including name, email, team (billing, tech, general), hire date, and active status. "
        "Use this table to analyse agent workload, performance, or team-level metrics."
    ),
    "categories_tbl": (
        "Defines ticket categories such as Billing or Technical, each with a description and SLA resolution target in hours. "
        "Use this table to filter tickets by type or to join SLA targets against actual resolution times."
    ),
    "tickets_tbl": (
        "Core table for support tickets, linking each ticket to a customer, an assigned agent, and a category, with status "
        "(open, pending, resolved), priority (low, medium, high, critical), subject, creation time, and resolution time. "
        "Central hub for most queries — joins to all other tables."
    ),
    "interactions_tbl": (
        "Logs every agent-customer interaction (call, email, or chat) against a ticket, with notes and a timestamp. "
        "Use this table to count touchpoints per ticket, measure response activity, or analyse interaction types."
    ),
    "products_tbl": (
        "Product catalog listing each product's name, optional version string, and category (SaaS, Hardware, API). "
        "Use this table to identify which products are most frequently mentioned in tickets via ticket_products_tbl."
    ),
    "ticket_products_tbl": (
        "Junction table that maps tickets to the products they relate to, enabling many-to-many relationships. "
        "Use this table to find tickets affecting a specific product or to count product-related support volume."
    ),
    "feedback_tbl": (
        "Stores post-resolution customer satisfaction (CSAT) feedback: a 1–5 rating and an optional text comment, "
        "linked to both the ticket and the customer. Use this table for CSAT analysis, low-score alerts, or agent scoring."
    ),
    "escalations_tbl": (
        "Tracks ticket escalations, recording the originating agent, the receiving agent, a reason, and a timestamp. "
        "Use this table to identify agents or ticket types with high escalation rates and to measure escalation frequency."
    ),
}


def load_schema(xlsx_path: str) -> list[TableSchema]:
    """
    Parse the 'Table Metadata' sheet from the xlsx file into TableSchema objects.
    One TableSchema per unique table name, preserving column order.

    param xlsx_path: Path to the Customer Service Tables xlsx file.
    """
    df = pd.read_excel(xlsx_path, sheet_name="Table Metadata")

    # Preserve insertion order — dict keeps insertion order in Python 3.7+.
    tables: dict[str, list[ColumnInfo]] = {}

    for _, row in df.iterrows():
        table_name = str(row["Table Name"]).strip()
        relationships = row["Relationships"]

        col = ColumnInfo(
            name=str(row["Column Name"]).strip(),
            data_type=str(row["Data Type"]).strip(),
            nullable=str(row["Nullable"]).strip().upper() == "YES",
            description=str(row["Description"]).strip(),
            relationships=None if pd.isna(relationships) else str(relationships).strip(),
        )

        if table_name not in tables:
            tables[table_name] = []
        tables[table_name].append(col)

    return [
        TableSchema(
            name=name,
            description=_TABLE_DESCRIPTIONS.get(name, ""),
            columns=cols,
        )
        for name, cols in tables.items()
    ]


if __name__ == "__main__":
    l = load_schema()
    