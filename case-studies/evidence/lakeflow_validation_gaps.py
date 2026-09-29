"""Two lakeflow_framework validation gaps, reproduced without Spark (repos/lakeflow_framework.md).

1. The engine and CI validate with jsonschema.Draft7Validator (utility.py:113, scripts/validate_dataflows.py:335).
   Draft 7 predates the `dependentSchemas` keyword (2019-09), which carries the per-type rules in the
   legacy schemas (9 occurrences in 6 schema files), so those rules are silently ignored.
2. constants.py:113 declares MAIN_SPEC_FILE_SUFFIX: tuple = ("_main.json"). Without a trailing comma this is a
   str, so `any(path.endswith(s) for s in suffix)` iterates characters and accepts any path ending in one of
   "_main.json"'s characters.

    pip install jsonschema && python lakeflow_validation_gaps.py
"""
import jsonschema as js

schema = {"type": "object",
          "properties": {"sourceType": {"type": "string"}, "sourceDetails": {"type": "object"}},
          "dependentSchemas": {"sourceType": {"properties": {"sourceDetails": {
              "required": ["table"], "additionalProperties": False, "properties": {"table": {"type": "string"}}}}}}}
bad = {"sourceType": "delta", "sourceDetails": {"databaseTYPO": "x", "bogusKey": 123}}
print("Draft7Validator errors     :", [e.message for e in js.Draft7Validator(schema).iter_errors(bad)])
print("Draft202012Validator errors:", [e.message for e in js.Draft202012Validator(schema).iter_errors(bad)])

suffix = ("_main.json")  # verbatim: a str, not a tuple
for p in ["orders_main.json", "orders_dqe.json", "README.rst", "notes.txt"]:
    print(f"{p:18} accepted as a main spec? {any(p.endswith(s) for s in suffix)}")

# Observed (jsonschema 4.x):
# Draft7Validator errors     : []
# Draft202012Validator errors: ["'table' is a required property", "Additional properties are not allowed (...)"]
# orders_main.json   accepted as a main spec? True
# orders_dqe.json    accepted as a main spec? True     <- an expectations file passes the "main spec" check
# README.rst         accepted as a main spec? False
# notes.txt          accepted as a main spec? False
