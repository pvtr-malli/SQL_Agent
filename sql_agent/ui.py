import gradio as gr
import httpx

API_BASE = "http://localhost:8000"


def build_index() -> str:
    """
    Call POST /index and return a status string.
    """
    try:
        r = httpx.post(f"{API_BASE}/index", timeout=120)
        data = r.json()
        if r.status_code != 200:
            return f"Error {r.status_code}: {data.get('detail', data)}"
        return (
            f"✓ Indexed {data['tables_indexed']} tables\n"
            f"Latency: {data['latency_ms']} ms"
        )
    except httpx.ConnectError:
        return "Cannot connect to API — is the server running on port 8000?"


def retrieve_tables(question: str) -> str:
    """
    Call GET /retrieve and format the returned tables.

    param question: Natural language question from the user.
    """
    if not question.strip():
        return "Enter a question first."
    try:
        r = httpx.get(f"{API_BASE}/retrieve", params={"question": question}, timeout=30)
        data = r.json()
        if r.status_code != 200:
            return f"Error {r.status_code}: {data.get('detail', data)}"

        lines = []
        for t in data["tables"]:
            cols = ", ".join(t["columns"])
            lines.append(f"**{t['name']}**  (score: {t['score']})\n  columns: {cols}")
        lines.append(f"\n_Retrieval latency: {data['retrieval_latency_ms']} ms_")
        return "\n\n".join(lines)
    except httpx.ConnectError:
        return "Cannot connect to API — is the server running on port 8000?"


def clear_cache() -> str:
    try:
        r = httpx.delete(f"{API_BASE}/cache", timeout=10)
        data = r.json()
        if r.status_code != 200:
            return f"Error {r.status_code}: {data.get('detail', data)}"
        return f"✓ Cleared {data['entries_cleared']} cached entries"
    except httpx.ConnectError:
        return "Cannot connect to API — is the server running on port 8000?"


def get_metrics() -> str:
    try:
        r = httpx.get(f"{API_BASE}/metrics", timeout=10)
        data = r.json()
        if r.status_code != 200:
            return f"Error {r.status_code}: {data.get('detail', data)}"

        req = data["requests"]
        qua = data["quality"]
        lat = data["latency_avg_ms"]

        return (
            f"### 📊 Requests\n"
            f"- Total: **{req['total']}** | Success: **{req['success']}** | Failed: **{req['failed']}**\n"
            f"- Cache hits: **{req['cache_hits']}** ({req['cache_hit_rate_pct']}%)\n\n"
            f"### 🔍 Quality\n"
            f"- Validation failures (≥2 attempts): **{qua['validation_failures']}** ({qua['validation_failure_rate_pct']}%)\n"
            f"- Agentic loop triggered: **{qua['agentic_triggered']}** ({qua['agentic_rate_pct']}%)\n"
            f"- Low retrieval score (< {qua['low_score_threshold']}): **{qua['low_score_retrievals']}** ({qua['low_score_rate_pct']}%)\n\n"
            f"### ⚡ Avg Latency\n"
            f"- RAG: **{lat['rag']} ms** | LLM: **{lat['llm']} ms** | Validation: **{lat['validate']} ms**\n"
            f"- Total: **{lat['total']} ms**"
        )
    except httpx.ConnectError:
        return "Cannot connect to API — is the server running on port 8000?"


def generate_sql(question: str) -> str:
    """
    Call POST /query and return the generated SQL.

    param question: Natural language question from the user.
    """
    if not question.strip():
        return "Enter a question first."
    try:
        r = httpx.post(f"{API_BASE}/query", json={"question": question}, timeout=60)
        data = r.json()
        if r.status_code != 200:
            return f"Error {r.status_code}: {data.get('detail', data)}"
        cache_label = " | ⚡ cache hit" if data.get("cache_hit") else ""
        return (
            f"{data['sql']}\n\n"
            f"-- attempts: {data['attempts']} | "
            f"tables: {', '.join(data.get('tables_used', []))} | "
            f"{data['latency_ms']} ms{cache_label}"
        )
    except httpx.ConnectError:
        return "Cannot connect to API — is the server running on port 8000?"


with gr.Blocks(title="SQL Agent", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# SQL Agent")

    with gr.Tab("Index"):
        gr.Markdown("Build (or rebuild) the vector index from the schema file.")
        index_btn = gr.Button("Build Index", variant="primary")
        index_out = gr.Textbox(label="Result", interactive=False)
        index_btn.click(fn=build_index, outputs=index_out)

        gr.Markdown("---")
        gr.Markdown("Clear the query cache. Do this after rebuilding the index so stale SQL is not served.")
        cache_btn = gr.Button("Clear Cache", variant="stop")
        cache_out = gr.Textbox(label="Result", interactive=False)
        cache_btn.click(fn=clear_cache, outputs=cache_out)

    with gr.Tab("Retrieve"):
        gr.Markdown("Inspect which tables the RAG retriever selects — no LLM call.")
        retrieve_in = gr.Textbox(label="Question", placeholder="Which agents had the most escalations?")
        retrieve_btn = gr.Button("Retrieve Tables", variant="primary")
        retrieve_out = gr.Markdown()
        retrieve_btn.click(fn=retrieve_tables, inputs=retrieve_in, outputs=retrieve_out)

    with gr.Tab("Query"):
        gr.Markdown("Generate SQL for a natural language question.")
        query_in = gr.Textbox(
            label="Question",
            placeholder="Find agents with CSAT below 3 who handled more than 10 tickets last month.",
            lines=3,
        )
        query_btn = gr.Button("Generate SQL", variant="primary")
        query_out = gr.Code(language="sql", label="Generated SQL")
        query_btn.click(fn=generate_sql, inputs=query_in, outputs=query_out)

    with gr.Tab("Metrics"):
        gr.Markdown("Live runtime metrics — request counts, quality signals, and average latency.")
        metrics_btn = gr.Button("Refresh Metrics", variant="primary")
        metrics_out = gr.Markdown()
        metrics_btn.click(fn=get_metrics, outputs=metrics_out)


if __name__ == "__main__":
    demo.launch()
