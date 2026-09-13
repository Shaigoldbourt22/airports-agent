# 13. Auth

The app itself has no login page, no password database, no session cookies.
Azure Container Apps has a feature called EasyAuth that sits in front of the
container. It handles the whole Google sign-in dance and then forwards the
request with a header, `x-ms-client-principal`, containing the signed-in
user's claims.

The app base64-decodes that header and pulls out the email address. That is
the user id. Locally there is no header, so the user is `"local"`.

There *is* an allowlist — the `ALLOWED_USERS` environment variable. It is
deliberately left empty in production, so anyone with a Google account can
sign in. Sign-in is not a gate here; it exists to keep one person's chat
history separate from another's.

The evaluation deployment is the exception. It has no sign-in in front of it,
because an automated test has no Google identity to present. So it sets
`EVAL_TOKEN`, and every request must carry that token as a bearer header. The
token **replaces** the allowlist rather than adding to it, and the comparison
uses `secrets.compare_digest` so timing cannot leak it. Production leaves
`EVAL_TOKEN` unset, which means that path is dead code there.

Rejections — bad token, blocked account — are logged with the status code, so
you can see them in Log Analytics.
