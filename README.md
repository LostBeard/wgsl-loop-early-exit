# wgsl-loop-early-exit

A WebGPU compute shader with nested loops gives wrong output on an AMD Radeon RX 590 in Chrome (D3D12): after the
first two iterations of its outer loop, the output no longer matches. The same shader is correct on an NVIDIA RTX 4070
in Chrome. No SpawnDev code runs on the page: plain WebGPU and one WGSL file.

Live page: https://lostbeard.github.io/wgsl-loop-early-exit/ (needs WebGPU; run it in Chrome on Windows with an AMD GPU).

## Results

| GPU / browser | Result |
|---|---|
| NVIDIA RTX 4070, Chromium, Playwright build 1248 (Windows, D3D12) | 6528 of 6528 right |
| AMD Radeon RX 590 (device 0x67df), Chrome 158 (installed build; headless and headed), D3D12, AMD driver 31.0.21925.1001, Windows 10 19045 | **136 of 6528 right**: first wrong entry at index 136 (table 2, entry 0), got 0 (its initial value), expected 512 |

The same C# kernel through SpawnDev.ILGPU's CUDA and OpenCL backends is right on the RTX 4070, and the same algorithm
over OpenCL on the RX 590 passes SpawnDev.Codecs' byte-identity tests; the failing combination here is WGSL on D3D12 on
that card. naga validates the shader ("Validation successful").

## What it does

One dispatch of one workgroup (`@workgroup_size(64)`; only invocation 0 does work, the others return at once). That
invocation computes libwebp's VP8 level-cost table (`VP8CalculateLevelCosts`, 6,528 ints), three loops deep:

- an outer `loop` over 96 tables (`if (!(i < 96)) { break; }`),
- a `loop` over 67 levels per table (`v_2 <= 67`),
- per level, the suspect innermost `loop`: its break condition is a bool carried across iterations (`v_15`), set from
  `pattern != 0` (compared unsigned, `bitcast<u32>(pattern) > 0`), where `pattern` was read from a storage buffer before
  the loop; it walks at most 9 bits. The loop body reads storage inside an `if` on the current bit
  (`param1`, `param3`) and contains no barrier, no atomic and no call. The only write, to `param2`, is after the loop
  and is never read back by the shader.

All three storage bindings are declared `read_write` (`param1`, `param2`, `param3`); `param1` and `param3` are only read.

Replacing just the innermost loop by a fixed walk over the 9 bits (the same sums by construction, `for (k < 9)`) makes
the whole table right on the RX 590 (6528 of 6528), so the data-dependent innermost loop matters. Not reduced beyond
that: this is the generated shader itself, `levelcost_while.wgsl`, unmodified (it is the WGSL of a C# loop; `enable f16`
is dropped at load when the adapter lacks `shader-f16`, nothing in the shader uses it).

## Files

- `index.html`: the page (requests the adapter, runs one dispatch, compares, prints the result).
- `levelcost_while.wgsl`: the shader, as SpawnDev.ILGPU 5.4.46 generated it (line endings normalized to LF).
- `data.json`: inputs and the expected output.
- `make_data.py`: how `data.json` was made from libwebp's tables (see NOTICE).

Found 2026-11-24 while porting libwebp's lossy encoder to SpawnDev.Codecs, where the fixed walk is marked as a
workaround.
