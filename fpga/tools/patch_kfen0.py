import re
p = r"source\top.v"
b = open(p, "rb").read()
n = b.count(b"KF_EN         (1'b1)")
print("occurrences of KF_EN (1'b1):", n)
if n != 1:
    raise SystemExit("unexpected count, abort")
b2 = b.replace(b"KF_EN         (1'b1)", b"KF_EN         (1'b0)")
open(p, "wb").write(b2)
print("patched KF_EN -> 1'b0 (bytes:", len(b), "->", len(b2), ")")
