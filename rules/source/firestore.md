Firestore uses the existing `(default)` Native mode database in the app region. Do not create a second Firestore database in Terraform or from a laptop.

Keep documents small (under a few kilobytes) and avoid sustained writes faster than once per second to the same document. Do not enable point-in-time recovery or scheduled backups unless the pull request explicitly approves the cost.

Write idempotency keys (`processed/{job}/items/{id}`) only after the external side effect (such as a customer reply or ticket update) has succeeded.

Use lease locks (`locks/{job}`) with an expiration timestamp so a crashed run cannot lock a job forever.

Replace reference/master collections by writing a new generation and flipping a pointer document (`meta/masters`), never by deleting and refilling live documents in place.
