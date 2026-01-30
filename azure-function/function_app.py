import azure.functions as func
import logging
import json
import re
import os
import uuid
from datetime import datetime

from azure.data.tables import TableServiceClient


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def get_table_client():
    conn_str = os.environ.get("TABLES_CONNECTION_STRING")
    table_name = os.environ.get("TABLE_NAME", "TextAnalysisResults")

    if not conn_str:
        raise ValueError("Missing TABLES_CONNECTION_STRING in environment variables.")

    service = TableServiceClient.from_connection_string(conn_str=conn_str)
    table_client = service.get_table_client(table_name=table_name)

    # Safe to call even if it already exists
    try:
        table_client.create_table()
    except Exception:
        pass

    return table_client


@app.route(route="TextAnalyzer", methods=["GET", "POST"])
def TextAnalyzer(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Text Analyzer API was called!")

    text = req.params.get("text")
    if not text:
        try:
            req_body = req.get_json()
            text = req_body.get("text")
        except ValueError:
            pass

    if not text:
        instructions = {
            "error": "No text provided",
            "howToUse": {
                "option1": "Add ?text=YourText to the URL",
                "option2": "Send a POST request with JSON body: {\"text\": \"Your text here\"}"
            }
        }
        return func.HttpResponse(
            json.dumps(instructions, indent=2),
            mimetype="application/json",
            status_code=400
        )

    # Analyze
    words = text.split()
    word_count = len(words)
    char_count = len(text)
    char_count_no_spaces = len(text.replace(" ", ""))
    sentence_count = len(re.findall(r"[.!?]+", text)) or 1
    paragraph_count = len([p for p in text.split("\n\n") if p.strip()])
    reading_time_minutes = round(word_count / 200, 1)
    avg_word_length = round(char_count_no_spaces / word_count, 1) if word_count > 0 else 0
    longest_word = max(words, key=len) if words else ""

    analyzed_at = datetime.utcnow().isoformat()
    preview = text[:100] + "..." if len(text) > 100 else text
    record_id = str(uuid.uuid4())

    response_data = {
        "id": record_id,
        "analysis": {
            "wordCount": word_count,
            "characterCount": char_count,
            "characterCountNoSpaces": char_count_no_spaces,
            "sentenceCount": sentence_count,
            "paragraphCount": paragraph_count,
            "averageWordLength": avg_word_length,
            "longestWord": longest_word,
            "readingTimeMinutes": reading_time_minutes
        },
        "metadata": {
            "analyzedAt": analyzed_at,
            "textPreview": preview
        }
    }

    # Persist to Azure Table Storage
    try:
        table_client = get_table_client()

        # Table entities MUST have PartitionKey and RowKey
        entity = {
            "PartitionKey": "TextAnalyzer",
            "RowKey": record_id,

            # Store JSON fields as strings (simple + reliable)
            "analysisJson": json.dumps(response_data["analysis"]),
            "metadataJson": json.dumps(response_data["metadata"]),
            "originalText": text,
            "createdAt": analyzed_at
        }

        table_client.create_entity(entity=entity)

    except Exception as e:
        logging.exception("Failed to write to Table Storage.")
        # Still return analysis even if persistence fails
        response_data["storageWarning"] = str(e)

    return func.HttpResponse(
        json.dumps(response_data, indent=2),
        mimetype="application/json",
        status_code=200
    )

@app.route(route="GetAnalysisHistory", methods=["GET"])
def GetAnalysisHistory(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("GetAnalysisHistory API was called!")

    # limit param (default 10)
    limit_str = req.params.get("limit", "10")
    try:
        limit = int(limit_str)
    except ValueError:
        limit = 10

    # keep it reasonable
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50

    try:
        table_client = get_table_client()

        # Query newest first (Timestamp is a system property)
        # We store everything under PartitionKey='TextAnalyzer'
        entities = table_client.query_entities(
            query_filter="PartitionKey eq 'TextAnalyzer'",
            results_per_page=limit
        )

        results = []
        count = 0

        for e in entities:
            if count >= limit:
                break

            analysis = json.loads(e.get("analysisJson", "{}"))
            metadata = json.loads(e.get("metadataJson", "{}"))

            results.append({
                "id": e.get("RowKey"),
                "analysis": analysis,
                "metadata": metadata
            })

            count += 1

        return func.HttpResponse(
            json.dumps({"count": count, "results": results}, indent=2),
            mimetype="application/json",
            status_code=200
        )

    except Exception as ex:
        logging.exception("Failed to read from Table Storage.")
        return func.HttpResponse(
            json.dumps({"error": "Failed to fetch history", "details": str(ex)}, indent=2),
            mimetype="application/json",
            status_code=500
        )

