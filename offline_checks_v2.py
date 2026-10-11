import json
import sys

sys.path.insert(0, "/home/z/parwa/backend")
from app.core.superglue_tool_generator import (  # noqa: E402
    _extract_markers,
    _stitch_transforms,
    _validate_marker_placement,
)

# 1) extraction: transform fields only
td = {
    "steps": [
        {"id": "s1", "config": {"type": "transform", "transformCode": "@@T1@@"}},
        {"id": "s2", "config": {"type": "request", "url": "postgres://x", "body": "@@T2@@"}},
    ],
    "outputTransform": "@@T3@@",
}
assert _extract_markers(td) == ["T1", "T3"], _extract_markers(td)

# 2) placement validator: body marker rejected
err = _validate_marker_placement(td)
assert err and "body" in err, err

# 3) bare arrow body rejected
td2 = {"steps": [{"id": "s", "config": {"type": "request", "body": "(sourceData) => ({q:1})"}}]}
err2 = _validate_marker_placement(td2)
assert err2 and "bare arrow" in err2, err2

# 4) template-ref body + input-ref body pass
td3 = {
    "steps": [
        {"id": "s1", "config": {"type": "request", "body": '{"query": "SELECT * FROM t WHERE email = \'<<customerEmail>>\'"}'}},
        {"id": "s2", "config": {"type": "request", "body": "<<(sourceData) => sourceData.s1.data>>"}},
        {"id": "s3", "config": {"type": "transform", "transformCode": "@@T1@@"}},
    ]
}
assert _validate_marker_placement(td3) is None, _validate_marker_placement(td3)
assert _extract_markers(td3) == ["T1"]

# 4b) inline-JS template-ref body REJECTED (quote-soup class)
td4 = {"steps": [{"id": "s", "config": {"type": "request", "body": '<<(sourceData) => \'{"query": "UPDATE t SET x = \'" + sourceData.s1.data[0].id + "\'\'"}\'>>'}}]}
err4 = _validate_marker_placement(td4)
assert err4 and "inline JS" in err4, err4

# 4c) object body REJECTED
td5 = {"steps": [{"id": "s", "config": {"type": "request", "body": {"query": "SELECT 1"}}}]}
err5 = _validate_marker_placement(td5)
assert err5 and "never an object" in err5, err5

# 4d) verified two-step pattern PASSES
td6 = {
    "steps": [
        {"id": "s1", "config": {"type": "transform", "transformCode": "@@T1@@"}},
        {"id": "s2", "config": {"type": "request", "body": "<<(sourceData) => sourceData.s1.data>>"}},
    ]
}
assert _validate_marker_placement(td6) is None, _validate_marker_placement(td6)

# 5) stitching untouched template-ref bodies, resolves transform markers
out = _stitch_transforms(td3, {"T1": "(sourceData) => sourceData.s1.data[0]"})
assert out and "@@" not in json.dumps(out)
assert out["steps"][1]["config"]["body"].startswith("<<(")

print("OFFLINE v2: ALL PASS")
