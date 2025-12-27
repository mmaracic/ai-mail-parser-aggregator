# README

## Application functions

### Mail fetching
* Fetches an email and processes and separates components: subject, sender, recipient, body and attachments.
* Generic Python libraries used, no custom mail provider services or libraries.

### Mail processing
* Only mails from listed senders are processed, the rest are dismissed
* Mail body is stripped of xml/html data to reduce size and then reduced to the most interesting knowledge. Processed emails are stored and the processing itself is audited.

### LLM
* Used to extract interesting knowledge from the reduced/trimmed body of the emails.

### Memgraph graph database
* Memgraph docker compose with database SSL, authentication requested and init script that sets up a user.
* Lab has quick connect disabled.
* Memgraph is used to store knowledge base about interesting and novel concepts reported in emails.

### Azure Cosmos
* Application uses Azure Cosmos to store configuration and audit data.

### Azure Blob Storage
* Blob storage is used to store interesting email for possible reprocessing.

## Running the application
Run the application with:
```
uv run -m  application
```
