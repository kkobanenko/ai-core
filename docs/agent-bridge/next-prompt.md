# WAIT — S1-start governance draft review

Do not continue automatically.

Current state:

- platform-control draft PR #295 is `OPEN/DRAFT/MERGEABLE`;
- exact base: `35a922ceacb51ff2e8e8ccacc00291fbd2155b52`;
- exact head: `44d30f1a81fe7736c83a6f49ce7fde5c91412b08`;
- exact-head Infrastructure CI run `34532744201` is green;
- authoritative platform-control main remains `35a922ce...` and still has S1
  start false;
- AI Core main remains `7569441c...`;
- no S1 source work has started.

Wait for external architecture/governance review and a new explicit operator
instruction. PR #295 must not be merged without separate authorization.

Even after that gate merge, runtime, service, transports, executor, provider
calls, consumer changes, infrastructure/deployment, release/tag, new provider
identities, and `STT_SEGMENTS` remain unauthorized. A future AI Core S1 PR must
remain draft and requires its own separate merge authorization.
