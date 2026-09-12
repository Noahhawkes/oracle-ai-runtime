# HYDRA Lane Map v0.1

ORACLE frontend is the mouth.
HYDRA is the lane router underneath.

## Input Types

- witness receipt
- artifact registration
- source retrieval
- file display
- canon proposal
- external action
- local reversible action
- irreversible action

## Routing

witness receipt -> Witness Head
artifact registration -> Artifact Registry Head
source retrieval -> Retrieval Head
file display -> Retrieval Head
canon proposal -> Canon Head
external action -> Guard Head
local reversible action -> Guard Head if file write, otherwise safe lane
irreversible action -> Guard Head always

## Failure Mode Observed

Large conceptual prompts are being routed into Guard as if they are executable irreversible actions.

## Fix Direction

Classify intent before Guard.
Only route to Guard when an operation writes files, changes state, publishes, deletes, moves, sends, pushes, or promotes durable memory.
