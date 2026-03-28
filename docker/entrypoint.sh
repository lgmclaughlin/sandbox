#!/bin/bash

# Container keepalive entrypoint.
# The container stays alive waiting for sessions. Each `sandbox attach`
# or `sandbox start` (with attach) runs session-wrapper.sh as a
# separate session with its own ID, logging, and exit trap.

exec sleep infinity
