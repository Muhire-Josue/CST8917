# Database Choice

## Choice
I selected **Azure Table Storage** to persist Text Analyzer results.

## Justification
The function produces simple JSON records that do not require relational structure or complex queries. Azure Table Storage is lightweight, low-cost, and integrates easily with Azure Functions using the Python SDK, making it well suited for a serverless lab scenario.

## Alternatives Considered
Cosmos DB offers more advanced querying but adds unnecessary complexity. Azure SQL requires schema design and is heavier than needed. Blob Storage is better for files than structured records.

## Cost Considerations
Azure Table Storage pricing is based on storage and transactions. For a small student workload, the cost remains minimal.
