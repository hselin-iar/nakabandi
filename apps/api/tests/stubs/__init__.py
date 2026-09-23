"""Stub facades for pipeline tests (DOC 4 A6 STUB/MOCK STRATEGY).

Each stub returns deterministic canned outputs matching LC-4 shapes. They stand in
for graph, forecast, interception and alerting until Sync 3, when real facades replace
them one at a time.  The golden test re-runs without modification after each swap.
"""
