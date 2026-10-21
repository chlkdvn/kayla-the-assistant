# Kayla memory (long-term)

Kayla remembers things across conversations using a small local **vector memory**,
and it does it without bloating the prompt.

## The idea (why it's token-cheap)

The model is stateless — anything it uses for a reply must be in its context at
that moment, and there is no way to make it "aware" of a memory without putting
that memory into context. The trick is **what** you put in:

- **Store everything on disk**, never in the base prompt.
- Each memory is turned into an *embedding* (a vector of numbers capturing its
  meaning).
- To recall, the query is embedded too and the **closest few** memories are found
  by cosine similarity — only those get injected.

So Kayla can remember unlimited things while only ever sending the handful that are
relevant right now. That's retrieval-augmented generation (RAG).

## How Kayla uses it

Realtime memory works in three ways:

- **`remember`** — saves a clear, self-contained fact ("Their dog is named Rex").
  Triggered whenever the user shares something personal or worth keeping.
- **`recall`** — searches the notes with a specific query. Kayla is prompted to
  call it proactively whenever a question might touch something told to her
  before, and it surfaces only the closest few memories.
- **Auto-capture (on by default):** beyond what Kayla chooses to save, everything
  you say is transcribed and stored automatically, so nothing is missed — you
  never have to tell it to remember. Turn it off with
  `KAYLA_MEMORY_AUTO_CAPTURE=false` to go back to Kayla-decides-only. Dictation
  in typing mode is never stored.

You'll see `[Remembered: ...]` and `[Checked memory.]` in the terminal.

## Modules

- `memory/store.py` — `MemoryStore`: save to a JSON file, recall top-K by cosine
  similarity. Pure logic, no model required (tested with a fake embedder).
- `memory/fastembed_embedder.py` — text → vector with a local ONNX model
  (fastembed). No API key, no network call at recall time; the model downloads
  once on first use. Behind the same `Embedder` interface, so another embedder
  can swap in.
- `realtime/options.py` / `realtime/gemini_session.py` — the `remember`/`recall`
  tool schemas and their handlers.

## Configuration

```text
KAYLA_MEMORY_ENABLED=true                 # set false to drop the memory tools
KAYLA_MEMORY_PATH=kayla_memory.json         # where memories are stored (gitignored)
KAYLA_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
KAYLA_MEMORY_TOP_K=5                      # how many memories to pull per recall
```

## Notes

- Memories persist in `kayla_memory.json` between runs; delete the file to wipe
  Kayla's memory.
- Deleting the file is also required when the embedding model changes: vectors
  from different models have different widths and are ignored on recall.
- Embedding runs locally and is free. The savings are still large: you never
  resend the whole memory, only the relevant few.
