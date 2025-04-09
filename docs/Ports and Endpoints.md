## Ports and Endpoints

### [[API]]

* Port 4200
* Endpoints
  * POST /completions
  * POST /embeddings
  * GET /models/{model_id}
  * GET /models
  * POST /chat/completions
  
### [[Brain]]

* Port 4207
* Endpoints
  * buffer
    * POST /buffer/conversation
    * GET /buffer/conversation
  * scheduler
    * POST /scheduler/callback
    * POST /scheduler/job
    * GET /scheduler/job
    * DELETE /scheduler/job/{id}
  * memory
    * POST /memory
    * POST /memory/search/id
    * GET /memory
    * GET /memory/{id}
    * DELETE /memory/{id}
    * PUT /memory{id}
    * PATCH /memory/{id}
  * message
    * POST /message/incoming
  * mode
    * POST /status/mode/{mode}
    * GET /status/mode

### [[ChromaDB]]

* Port 4206
* Endpoints
  * memory
    * POST /memory/search/id
    * POST /memory
    * GET /memory
    * GET /memory/{id}
    * DELETE /memory/{id}
    * PUT /memory/{id}
    * PATCH /memory/{id}
  * summary
    * POST /summary
    * GET /summary/{id}
    * GET /summary/user/{user_id}
    * DELETE /summary/{id}
    * GET /summary/search
  * buffer
    * POST /buffer
    * GET /buffer
    * GET /buffer/{user_id}
    * DELETE /buffer/{user_id}

### [[Contacts]]

* Port 4202
* Endpoints
  * POST /contact
  * GET /contacts
  * PUT /contact/{id}
  * PATCH /contact/{id}
  * DELETE /contact/{id}
  * GET /search (?q=)

### [[iMessage]]

* Port 4204
* Endpoints
  * summary
    * POST /imessage/send
    * POST /imessage/recv

### [[Proxy]]

* Port 4205
* Endpoints
  * POST /from/imessage
  
### [[Scheduler]]

* Port 4201
* Endpoints
  * POST /jobs
  * DELETE /jobs/{id}
  * GET /jobs
  * POST /jobs/{id}/pause
  * POST /jobs/{id}/resume

### [[Summarize]]

* Port 4203
* Endpoints
  * GET /context/{user_id}
  * summary
    * POST /summary
    * GET /summary/{id}
    * DELETE /summary/{id}
    * GET /summary/user/{user id}
    * DELETE /summary/user/{user id}
    * GET /summary/search?q=
  * buffer
    * POST /buffer
    * GET /buffer
    * GET /buffer/{user id}
    * DELETE /buffer/{user id}