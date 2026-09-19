# Experiment 48 Environment

## Operating system

Ubuntu Linux

## Python

Python 3.11

Environment:

conda environment:

leandojo_v2_env


## Lean

Lean version:

4.27.0


Toolchain:

leanprover/lean4:v4.27.0


## LeanDojo

Package:

lean-dojo-v2

Version:

1.0.9


## Backend

Backend:

live_lean_tacticinfo_branch


Not used:

- Pantograph
- serialized proof state restoration


## Required Python packages

Main dependencies:

- lean-dojo-v2
- pantograph (available but not used in Exp48 execution)
- numpy
- pandas


## Repository checkout

Each repository must be checked out at the frozen commit recorded in:

artifacts/v48/frozen/experiment48_config.json


## Verification

Before execution:

1. verify frozen config hash
2. verify code lock
3. verify theorem selection hash
4. run preflight
5. execute pipeline