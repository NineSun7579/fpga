"""Plan relative C16 feature storage without assigning live FPGA DDR addresses.

The proposed layout is [channel_group, row, column, lane], with 16 uint8
lanes per word. Its compatibility with every legacy DMA/compute path must
be verified before using this plan as a hardware image.
"""

import argparse
import json
from pathlib import Path


def align16(size):
    return (size + 15) // 16 * 16


def plan(ir):
    tasks = ir["tasks"]
    tensors = ir["tensors"]
    produced = {task["output"]: task["id"] for task in tasks}
    aliases = {}
    for task in tasks:
        if task["op"] == "ChannelView":
            source = task["inputs"][0]
            root, base = aliases.get(source, (source, 0))
            shape = task["input_shapes"][0]
            offset = task["channel_start"] * shape[2] * shape[3]
            aliases[task["output"]] = (root, base + offset)
    roots = {name: aliases.get(name, (name, 0))[0] for name in tensors}
    last = {root: produced.get(root, -1) for root in roots.values()}
    for task in tasks:
        for name in task["inputs"]:
            root = roots[name]
            last[root] = max(last[root], task["id"])
    for name in ir["outputs"]:
        last[roots[name]] = len(tasks)
    allocations = {}
    active = []
    free = []
    highwater = 0

    def release(before):
        nonlocal active, free
        keep = []
        for end, start, size in active:
            if end < before:
                free.append((start, size))
            else:
                keep.append((end, start, size))
        active = keep
        merged = []
        for start, size in sorted(free):
            if merged and merged[-1][0] + merged[-1][1] == start:
                merged[-1] = (merged[-1][0], merged[-1][1] + size)
            else:
                merged.append((start, size))
        free = merged

    def allocate(name, birth):
        nonlocal highwater
        release(birth)
        size = align16(tensors[name]["bytes_u8_padded"])
        candidates = [(block_size, index, start) for index, (start, block_size) in enumerate(free)
                      if block_size >= size]
        if candidates:
            block_size, index, start = min(candidates)
            free.pop(index)
            if block_size > size:
                free.append((start + size, block_size - size))
        else:
            start = highwater
            highwater += size
        allocations[name] = {"offset": start, "bytes": size, "born_task": birth,
                             "last_consumer_task": last[name], "alias_of": None}
        active.append((last[name], start, size))

    for name in tensors:
        if name not in produced:
            allocate(name, -1)
    for task in tasks:
        name = task["output"]
        if name not in aliases:
            allocate(name, task["id"])
        else:
            root, delta = aliases[name]
            source = allocations[root]
            size = tensors[name]["bytes_u8_padded"]
            if delta < 0 or delta + size > source["bytes"]:
                raise ValueError(f"Channel view escapes parent allocation: {name}")
            allocations[name] = {"offset": source["offset"] + delta, "bytes": size,
                                 "born_task": task["id"], "last_consumer_task": last[root],
                                 "alias_of": root}
    owning = [(name, allocation) for name, allocation in allocations.items() if allocation["alias_of"] is None]
    # Independently verify byte overlap against task lifetime overlap, not only
    # the allocator free list. Inputs cannot be overwritten during their consumer.
    for index, (left_name, left) in enumerate(owning):
        for right_name, right in owning[index + 1:]:
            overlap_bytes = max(left["offset"], right["offset"]) < min(
                left["offset"] + left["bytes"], right["offset"] + right["bytes"])
            overlap_life = max(left["born_task"], right["born_task"]) <= min(
                left["last_consumer_task"], right["last_consumer_task"])
            if overlap_bytes and overlap_life:
                raise ValueError(f"Live buffer collision: {left_name}, {right_name}")
    return {"status": "relative_plan_only_no_board_ddr_assignment",
            "layout": "uint8 C16 [channel_group,row,column,lane]; byte lane0 is lowest address",
            "feature_arena_bytes": highwater,
            "all_independent_tensor_bytes": sum(tensors[name]["bytes_u8_padded"] for name, _ in owning),
            "allocations": allocations,
            "checks": {"live_owner_collision": "PASS", "alias_bounds": "PASS"},
            "limits": ["sequential tasks only; concurrent engines require new lifetimes",
                       "camera/ring/weight/reserved DDR mapping not assigned here",
                       "legacy packed-layout compatibility and DMA addressing not yet verified"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = plan(json.loads(args.ir.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("BUFFER_PLAN_PASS", "arena_bytes", result["feature_arena_bytes"],
          "independent_bytes", result["all_independent_tensor_bytes"])
