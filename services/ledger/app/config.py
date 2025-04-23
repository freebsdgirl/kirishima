BUFFER_DB = "./shared/db/ledger/buffer.db"

user_chunk_size          = 512     # the maximum number of tokens to process for user summarization
user_chunk_at            = 1024    # the number of tokens the buffer must contain before the oldest user chunk is summarized

user_summary_chunk_size  = 3       # the number of summaries to combine into a single summary
user_summary_chunk_at    = 5       # the number of summaries that must be present before the oldest summaries are combined
user_summary_tokens      = 64     # the maximum number of tokens for each summary

conversation_buffer_keep = 20