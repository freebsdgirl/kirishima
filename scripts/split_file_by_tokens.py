#!/usr/bin/env python

import argparse
from transformers import AutoTokenizer

def chunk_text_by_tokens(input_text, tokenizer, tokens_per_chunk):
    """
    Tokenizes the input text and splits it into chunks containing at most tokens_per_chunk tokens.
    The tokens are then decoded back into text.
    """
    # Tokenize the input text without adding special tokens.
    tokens = tokenizer.encode(input_text, add_special_tokens=False)
    
    # Split token list into chunks.
    token_chunks = [tokens[i:i+tokens_per_chunk] for i in range(0, len(tokens), tokens_per_chunk)]
    
    # Decode each chunk back into text.
    chunked_texts = [
        tokenizer.decode(chunk, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        for chunk in token_chunks
    ]
    return chunked_texts

def main():
    parser = argparse.ArgumentParser(
        description=("Split a text file into chunks based on the specified number of tokens "
                     "using the intfloat/e5-small-v2 model's tokenizer.")
    )
    parser.add_argument("filename", type=str, help="Path to the input text file.")
    parser.add_argument("tokens_per_chunk", type=int, help="Number of tokens per chunk.")

    args = parser.parse_args()

    # Read the entire file.
    try:
        with open(args.filename, "r", encoding="utf8") as file:
            text = file.read()
    except FileNotFoundError:
        print(f"Error: The file '{args.filename}' was not found.")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Load the tokenizer from the Hugging Face model. This will download the model if it is not already cached.
    tokenizer = AutoTokenizer.from_pretrained("intfloat/e5-small-v2")

    # Process the text to create chunks.
    chunked_texts = chunk_text_by_tokens(text, tokenizer, args.tokens_per_chunk)

    # Output each chunk. You could alternatively write these chunks to separate files.
    for idx, chunk in enumerate(chunked_texts, 1):
        print(f"--- Chunk {idx} (tokens: up to {args.tokens_per_chunk}) ---")
        print(chunk)
        print("\n")

if __name__ == "__main__":
    main()
