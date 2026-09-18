\# Partner Catalog Ingestion



A Python project for importing a partner's product catalog

from a REST API into PostgreSQL.



\## Business context



A company needs a local, structured copy of its partner's

product catalog for use by internal applications.



This project focuses on reliable data ingestion and validation.



\## Planned workflow



1\. Fetch all product pages from a local REST API.

2\. Save raw JSON responses.

3\. Validate and transform product records.

4\. Store valid records in PostgreSQL without creating duplicates.

5\. Log the import outcome and record rejection reasons.



\## Demo environment



The project will use a fixed sample dataset served through

a local API to make demonstrations repeatable and independent

of an external API.



\## Status



Under development. The ingestion pipeline is not implemented yet.

