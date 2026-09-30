"""Look-and-say: Conway's constant from the sequence, and the 92 elements found by the code.

The sequence 1, 11, 21, 1211, 111221, ... reads each term aloud to get the
next. Its lengths grow by a factor that tends to Conway's constant,
1.3035772690... This module finds that number three ways: from the ratio of
successive lengths, from the 92 "elements" into which every late term
splits (discovered here from the sequence, not typed in), and as a root of
the characteristic polynomial of their decay matrix.
"""

from __future__ import annotations

import argparse
import math
from decimal import Decimal, getcontext
from fractions import Fraction
from itertools import groupby
from pathlib import Path

# The state of the first-digit tracker keeps at most this many leading
# characters of the evolving string. Sixteen is plenty; the tests check that
# eight and thirty-two give the same answers.
PREFIX_CAP = 16

# The fewest terms over which main() judges when digits have settled.
SETTLE_HORIZON = 1000


def step(s: str) -> str:
    """Read a string of digits aloud: '1211' -> '111221'."""
    return "".join(f"{len(list(run))}{digit}" for digit, run in groupby(s))


def terms(n: int, seed: str = "1") -> list[str]:
    """The first n terms, starting from the seed."""
    out = [seed]
    while len(out) < n:
        out.append(step(out[-1]))
    return out[:n]


def first_digits(r: str, cap: int = PREFIX_CAP) -> set[str]:
    """Every digit that ever leads step^k(r), k = 0, 1, 2, ...

    This is exact, not a sampled horizon. It follows a bounded prefix of
    step^k(r). Reading a prefix aloud gets every run right except perhaps the
    last, which may have been cut short, so dropping the last count-digit
    pair leaves a true prefix of the next string. The prefix is then cut to
    `cap` characters. Each state is a function of the one before, so once a
    state repeats, the leading digits cycle forever and the set is complete.
    """
    state, whole = r, True
    seen: set[tuple[str, bool]] = set()
    leading: set[str] = set()
    while (state, whole) not in seen:
        seen.add((state, whole))
        leading.add(state[0])
        nxt = step(state)
        if whole:
            if len(nxt) > cap:
                state, whole = nxt[:cap], False
            else:
                state = nxt
        else:
            state = nxt[:-2][:cap]
            if len(state) < 2:
                raise ValueError(f"prefix of {r!r} too short to follow; raise cap")
    return leading


def splits(s: str, i: int) -> bool:
    """Does s split between s[:i] and s[i:] forever?

    step(xy) == step(x) + step(y) exactly when the last digit of x differs
    from the first digit of y. Reading aloud never changes a string's last
    digit, so s splits at i for every future step exactly when s[i-1] never
    leads step^k(s[i:]).
    """
    return s[i - 1] not in first_digits(s[i:])


def decompose(s: str) -> list[str]:
    """Split s into pieces that each evolve on their own, as finely as possible."""
    for i in range(1, len(s)):
        if splits(s, i):
            return decompose(s[:i]) + decompose(s[i:])
    return [s]


def discover(seed: str = "1") -> dict[str, list[str]]:
    """Every piece reachable from the seed, mapped to the pieces it becomes."""
    decay: dict[str, list[str]] = {}
    todo = [seed]
    while todo:
        piece = todo.pop()
        if piece not in decay:
            decay[piece] = decompose(step(piece))
            todo.extend(decay[piece])
    return decay


def elements(decay: dict[str, list[str]]) -> list[str]:
    """The pieces that recur: each can be reached from itself.

    From seed '1' these are Conway's 92 elements; the rest are the early
    terms that appear once and never again. Sorted longest first.
    """

    def reachable(piece: str) -> set[str]:
        seen: set[str] = set()
        stack = list(decay[piece])
        while stack:
            p = stack.pop()
            if p not in seen:
                seen.add(p)
                stack.extend(decay[p])
        return seen

    return sorted((p for p in decay if p in reachable(p)), key=lambda p: (-len(p), p))


def lengths(n: int, seed: str = "1") -> list[int]:
    """Exact lengths of the first n terms, by counting pieces, not building strings."""
    decay = discover(seed)
    counts = {seed: 1}
    out = []
    for _ in range(n):
        out.append(sum(c * len(p) for p, c in counts.items()))
        nxt: dict[str, int] = {}
        for p, c in counts.items():
            for child in decay[p]:
                nxt[child] = nxt.get(child, 0) + c
        counts = nxt
    return out


def decay_matrix(els: list[str], decay: dict[str, list[str]]) -> list[list[int]]:
    """M[i][j] = how many copies of element j element i becomes in one step."""
    index = {p: i for i, p in enumerate(els)}
    m = [[0] * len(els) for _ in els]
    for i, p in enumerate(els):
        for child in decay[p]:
            m[i][index[child]] += 1
    return m


# --- the characteristic polynomial, exactly -------------------------------


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for q in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % q == 0:
            return n == q
    d, r = n - 1, 0
    while d % 2 == 0:
        d, r = d // 2, r + 1
    for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):  # deterministic below 3.3e24
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _charpoly_mod(m: list[list[int]], p: int) -> list[int]:
    """Coefficients of det(xI - m) mod p, lowest degree first, via Hessenberg form."""
    n = len(m)
    h = [[v % p for v in row] for row in m]
    for k in range(1, n):
        pivot = next((i for i in range(k, n) if h[i][k - 1]), None)
        if pivot is None:
            continue
        if pivot != k:
            h[k], h[pivot] = h[pivot], h[k]
            for row in h:
                row[k], row[pivot] = row[pivot], row[k]
        inv = pow(h[k][k - 1], p - 2, p)
        for i in range(k + 1, n):
            u = h[i][k - 1] * inv % p
            if u:
                h[i] = [(a - u * b) % p for a, b in zip(h[i], h[k], strict=True)]
                for row in h:
                    row[k] = (row[k] + u * row[i]) % p
    polys = [[1]]
    for k in range(1, n + 1):
        prev = polys[k - 1]
        new = [0] + prev  # x * prev
        for d, c in enumerate(prev):
            new[d] = (new[d] - h[k - 1][k - 1] * c) % p
        t = 1
        for i in range(k - 1, 0, -1):
            t = t * h[i][i - 1] % p
            coef = t * h[i - 1][k - 1] % p
            for d, c in enumerate(polys[i - 1]):
                new[d] = (new[d] - coef * c) % p
        polys.append(new)
    return polys[n]


def charpoly(m: list[list[int]]) -> list[int]:
    """Exact integer coefficients of det(xI - m), lowest degree first.

    Computed modulo enough large primes to cover a proven bound on the
    coefficients, then put together with the Chinese remainder theorem. The
    coefficient of x^(n-k) is a sum of k-by-k principal minors, each at most
    the product of its rows' lengths (Hadamard), so every coefficient is at
    most the product over rows of (1 + row length).
    """
    log_bound = sum(math.log2(1 + math.sqrt(sum(v * v for v in row))) for row in m)
    need = 2 ** (math.ceil(log_bound) + 2)
    moduli, residues, modulus = [], [], 1
    p = 2**61 - 1
    while modulus <= need:
        while not _is_prime(p):
            p -= 2
        moduli.append(p)
        residues.append(_charpoly_mod(m, p))
        modulus *= p
        p -= 2
    coeffs = []
    for d in range(len(m) + 1):
        x = 0
        for q, res in zip(moduli, residues, strict=True):
            rest = modulus // q
            x += res[d] * rest * pow(rest, -1, q)
        x %= modulus
        coeffs.append(x - modulus if x > modulus // 2 else x)
    return coeffs


def divide_out(poly: list[int], root: int) -> tuple[list[int], int]:
    """Divide out (x - root) as many times as it goes; return quotient and count."""
    count = 0
    while len(poly) > 1:
        # synthetic division, highest degree first
        high = poly[::-1]
        quotient = [high[0]]
        for c in high[1:]:
            quotient.append(c + root * quotient[-1])
        if quotient.pop() != 0:
            break
        poly = quotient[::-1]
        count += 1
    return poly, count


def factor_trivial(poly: list[int]) -> tuple[dict[int, int], list[int]]:
    """Strip the factors x, x - 1 and x + 1; return their powers and what is left."""
    powers = {}
    for root in (0, 1, -1):
        poly, powers[root] = divide_out(poly, root)
    return powers, poly


def newton_root(poly: list[int], start: float, digits: int = 60) -> Decimal:
    """Polish a real root of an integer polynomial to `digits` digits."""
    getcontext().prec = digits + 10
    x = Decimal(start)
    deriv = [d * c for d, c in enumerate(poly)][1:]
    for _ in range(200):
        fx = sum(Decimal(c) * x**d for d, c in enumerate(poly))
        dfx = sum(Decimal(c) * x**d for d, c in enumerate(deriv))
        nxt = x - fx / dfx
        if nxt == x:
            break
        x = nxt
    return +x


def all_roots(poly: list[int], iterations: int = 2000) -> list[complex]:
    """Every complex root, by the Durand-Kerner iteration."""
    lead = poly[-1]
    monic = [c / lead for c in poly]
    n = len(poly) - 1
    roots = [(0.4 + 0.9j) ** k * 1.1 for k in range(n)]
    for _ in range(iterations):
        biggest = 0.0
        for i, z in enumerate(roots):
            num = 0j
            for c in reversed(monic):
                num = num * z + c
            den = 1 + 0j
            for j, w in enumerate(roots):
                if j != i:
                    den *= z - w
            delta = num / den
            roots[i] = z - delta
            biggest = max(biggest, abs(delta))
        if biggest < 1e-15:
            break
    return roots


# --- how fast the ratio gets there ----------------------------------------


def settled(ratios: list[Fraction], target: Decimal, digits: int) -> int | None:
    """First index after which every ratio agrees with target in its first `digits` digits.

    Agreeing in the first d digits means the same leading digits when cut
    off, not rounded: 1.30357... agrees with 1.3035772... in six.
    """
    scale = 10 ** (digits - 1)
    want = math.floor(target * scale)
    last_bad = None
    for n, r in enumerate(ratios):
        if math.floor(r * scale) != want:
            last_bad = n
    if last_bad == len(ratios) - 1:
        return None
    return 0 if last_bad is None else last_bad + 1


def chart(errors: list[float], rate: float, settle6: int, out: Path) -> None:
    """log10 |ratio - Conway's constant| against the term number, as an SVG."""
    w, h = 720, 380
    left, right, top, bottom = 64, 20, 36, 48
    n_max = len(errors)
    y_min, y_max = -14.0, 0.0

    def px(n: float) -> float:
        return left + (n - 1) / (n_max - 1) * (w - left - right)

    def py(v: float) -> float:
        v = min(max(v, y_min), y_max)
        return top + (y_max - v) / (y_max - y_min) * (h - top - bottom)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'font-family="system-ui, sans-serif" font-size="12">',
        f'<rect width="{w}" height="{h}" fill="#fff"/>',
        f'<text x="{left}" y="20" font-size="14" font-weight="600">How close '
        "length(n+1) / length(n) is to Conway's constant</text>",
    ]
    for v in range(0, -15, -2):
        y = py(v)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{w - right}" y2="{y:.1f}" stroke="#e5e5e5"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#555">1e{v}</text>'
        )
    for n in range(0, n_max + 1, 25):
        if n < 1:
            continue
        x = px(n)
        parts.append(
            f'<text x="{x:.1f}" y="{h - bottom + 18}" text-anchor="middle" fill="#555">{n}</text>'
        )
    parts.append(
        f'<text x="{(left + w - right) / 2}" y="{h - 10}" text-anchor="middle" fill="#555">'
        "term n</text>"
    )
    # the moment six digits hold for good
    x6 = px(settle6)
    parts.append(
        f'<line x1="{x6:.1f}" y1="{top}" x2="{x6:.1f}" y2="{h - bottom}" '
        'stroke="#c2410c" stroke-dasharray="4 3"/>'
    )
    parts.append(
        f'<text x="{x6 + 6:.1f}" y="{top + 14}" fill="#c2410c">first six digits right '
        f"for good from n = {settle6}</text>"
    )
    # the slope predicted by the second-largest eigenvalue, laid on the
    # upper envelope of the errors
    slope = math.log10(rate)
    start = 30
    lift = max(math.log10(e) - slope * n for n, e in enumerate(errors, start=1) if n >= start)
    y_a, y_b = lift + slope * start, lift + slope * n_max
    parts.append(
        f'<line x1="{px(start):.1f}" y1="{py(y_a):.1f}" x2="{px(n_max):.1f}" y2="{py(y_b):.1f}" '
        'stroke="#2563eb" stroke-width="1.5" stroke-dasharray="6 4"/>'
    )
    parts.append(
        f'<text x="{w - right}" y="{top + 44}" text-anchor="end" '
        f'fill="#2563eb">dashed: shrinking by |λ₂| / λ = {rate:.4f} per term</text>'
    )
    points = " ".join(
        f"{px(n):.1f},{py(math.log10(e)):.1f}" for n, e in enumerate(errors, start=1) if e > 0
    )
    parts.append(f'<polyline points="{points}" fill="none" stroke="#111" stroke-width="1.2"/>')
    parts.append("</svg>")
    out.write_text("\n".join(parts) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--terms", type=int, default=1000, help="compare length(n+1)/length(n) at this n"
    )
    parser.add_argument("--out", type=Path, help="write the convergence chart here")
    args = parser.parse_args(argv)
    if args.terms < 1:
        parser.error("--terms must be at least 1")

    decay = discover()
    els = elements(decay)
    transients = [t for t in terms(len(decay) - len(els)) if t not in els]
    print(f"pieces reachable from '1': {len(decay)}")
    print(f"  recurring (Conway's elements): {len(els)}, longest {len(els[0])} digits")
    print(f"  seen once, never again: {', '.join(transients)}")

    poly = charpoly(decay_matrix(els, decay))
    powers, rest = factor_trivial(poly)
    print(
        f"characteristic polynomial: x^{powers[0]} (x-1)^{powers[1]} (x+1)^{powers[-1]} "
        f"times a degree-{len(rest) - 1} factor"
    )
    lam = newton_root(rest, 1.3035772690342964, digits=50)
    roots = sorted(all_roots(rest), key=abs, reverse=True)
    second = roots[1]
    print(f"Conway's constant, root of that factor: {str(lam)[:52]}")
    print(f"next-largest roots: {second.real:+.6f} {second.imag:+.6f}i, modulus {abs(second):.6f}")

    # Whether digits have settled "for good" is judged over at least a
    # thousand terms, whatever --terms asks for: by then the error is below
    # 1e-48 and still shrinking, so no later ratio can undo 12 digits.
    horizon = max(args.terms, SETTLE_HORIZON)
    ls = lengths(horizon + 1)
    ratios = [Fraction(ls[n + 1], ls[n]) for n in range(horizon)]
    places = 50
    last = ratios[args.terms - 1]
    as_ratio = Decimal(last.numerator) / Decimal(last.denominator)
    same = f"{as_ratio:.{places}f}" == f"{lam:.{places}f}"
    print(
        f"length({args.terms + 1}) / length({args.terms}) "
        f"{'agrees' if same else 'does not agree'} with the root to {places} places"
    )

    print("\nratio length(n+1)/length(n) first agrees for good with Conway's constant in")
    for d in (2, 3, 4, 5, 6, 7, 8, 10, 12):
        n = settled(ratios, lam, d)
        print(f"  {d:2d} digits: from n = {n + 1 if n is not None else '(not yet)'}")

    if args.out:
        errors = [abs(float(r - Fraction(lam))) for r in ratios[:220]]
        rate = abs(second) / float(lam)
        chart(errors, rate, settled(ratios, lam, 6) + 1, args.out)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
