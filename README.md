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

## Deployment
Azure deployment branch is: azure-deployment
Deployment files added or changed are based on these two projects:
* https://github.com/mmaracic/ai-agent-azure-pcbuilder/blob/main/pcbuilder-api

* https://learn.microsoft.com/en-us/samples/azure-samples/fastapi-on-azure-functions/fastapi-on-azure-functions/
    * https://github.com/Azure-Samples/fastapi-on-azure-functions/

My project is more updated, with helpful hints and error descriptions.

### Running locally
Through task: func host start

Note: First time a runtime needs to be selected, select Python - usually under number 4. It is added to `local.settings.json` under FUNCTIONS_WORKER_RUNTIME.