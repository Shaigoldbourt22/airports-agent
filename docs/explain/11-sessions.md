# 11. Sessions

`app/sessions.py` keeps your chat history so you can close the tab and come
back. It is a *second* SQLite file, `sessions.db`, completely separate from the
read-only aviation database.

Two tables: `session` (id, user, title, last updated) and `message` (role,
text, attachment names, timestamp). The title is the first 80 characters of
your opening question.

Limits keep it from growing forever: 50 sessions per user, 50 messages per
session, oldest deleted first.

Only attachment **names** are stored, never contents. Replayed history is text
only — a 8 MB PDF is not sitting in the database.

Every query filters on `user_id`, so asking for someone else's session id
returns nothing rather than their conversation.

Now the interesting part. This file lives on an Azure Files share, which is
SMB, and SMB does not support the byte-range locks SQLite normally takes for
every transaction. That produced constant "database is locked" 500 errors in
production. Three settings fix it:

- `journal_mode=DELETE` — WAL needs shared memory, which SMB has not got.
- `locking_mode=EXCLUSIVE` — take one lock for the life of the process
  instead of one per transaction.
- a Python `Lock` — serialises writes inside the process.

Safe only because the app runs a single replica. Say that out loud before
anyone scales it.
