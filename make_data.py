"""Builds data.json for the level-cost while-loop repro: the constant table t (only the regions the shader reads), the
default coefficient probabilities and the expected level-cost table (VP8CalculateLevelCosts, computed here)."""
import json, re, sys

src = open(sys.argv[1], encoding='utf-8').read()   # SpawnDev.Codecs Vp8EncTables.g.cs (libwebp's tables)

def table(name):
    m = re.search(name + r'\s*=\s*\{(.*?)\};', src, re.S)
    return [int(x, 0) for x in re.findall(r'0x[0-9a-fA-F]+|\d+', m.group(1))]

entropy = table('VP8EntropyCost')
codes = table('VP8LevelCodes')
proba0 = table('VP8CoeffsProba0')
assert len(entropy) == 256 and len(codes) == 134 and len(proba0) == 1056, (len(entropy), len(codes), len(proba0))

ENTROPY, LEVEL_CODES = 0, 256 + 2048 + 17          # WebPLossyEncTables offsets baked into the shader
T_SIZE = LEVEL_CODES + 134
t = [0] * T_SIZE
t[ENTROPY:ENTROPY + 256] = entropy
t[LEVEL_CODES:LEVEL_CODES + 134] = codes

NUM_TYPES, NUM_BANDS, NUM_CTX, NUM_PROBAS, MAX_LEVEL, STRIDE = 4, 8, 3, 11, 67, 68

def bit_cost(bit, p):
    return entropy[255 - p] if bit else entropy[p]

expected = [0] * (NUM_TYPES * NUM_BANDS * NUM_CTX * STRIDE)
for task in range(NUM_TYPES * NUM_BANDS * NUM_CTX):
    ctx, band, ctype = task % NUM_CTX, (task // NUM_CTX) % NUM_BANDS, task // (NUM_CTX * NUM_BANDS)
    p = NUM_PROBAS * (ctx + NUM_CTX * (band + NUM_BANDS * ctype))
    tbl = STRIDE * (ctx + NUM_CTX * (band + NUM_BANDS * ctype))
    cost0 = bit_cost(1, proba0[p]) if ctx > 0 else 0
    base = bit_cost(1, proba0[p + 1]) + cost0
    expected[tbl] = bit_cost(0, proba0[p + 1]) + cost0
    for v in range(1, MAX_LEVEL + 1):
        pattern, bits = codes[(v - 1) * 2], codes[(v - 1) * 2 + 1]
        cost, i = 0, 2
        while pattern:
            if pattern & 1:
                cost += bit_cost(bits & 1, proba0[p + i])
            bits >>= 1; pattern >>= 1; i += 1
        expected[tbl + v] = base + cost

json.dump({'t': t, 'coeffs': proba0, 'expected': expected}, open(sys.argv[2], 'w'))
print('data.json:', len(t), 't,', len(proba0), 'coeffs,', len(expected), 'expected')
