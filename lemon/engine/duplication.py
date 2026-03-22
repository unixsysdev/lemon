"""MinHash / LSH duplication detection — direct port of duplication.rs + minhash.rs."""

from __future__ import annotations

import re
import struct
from collections import defaultdict
from pathlib import Path

from ..models import CodeChunk, DuplicateCluster, DuplicatePair, DuplicationConfig

# ---------------------------------------------------------------------------
# Constants matching the Rust implementation
# ---------------------------------------------------------------------------

_HASH_SEED_A: int = 0x9E3779B97F4A7C15
_HASH_SEED_B: int = 0xBF58476D1CE4E5B9
_HASH_SEED_C: int = 0x94D049BB133111EB
_MASK64: int = (1 << 64) - 1


# ---------------------------------------------------------------------------
# Code normalization
# ---------------------------------------------------------------------------

_NORMALIZE_WS = re.compile(r"\s+")
_NORMALIZE_DIGITS = re.compile(r"\d+")


def normalize_code(source: str) -> str:
    """Normalize code for comparison: collapse whitespace, digits→N, lowercase."""
    s = _NORMALIZE_WS.sub(" ", source)
    s = _NORMALIZE_DIGITS.sub("N", s)
    return s.lower().strip()


# ---------------------------------------------------------------------------
# Shingling
# ---------------------------------------------------------------------------

def shingle(text: str, n: int = 3) -> list[str]:
    """Generate character n-gram shingles from text."""
    if len(text) < n:
        return [text] if text else []
    return [text[i : i + n] for i in range(len(text) - n + 1)]


# ---------------------------------------------------------------------------
# MinHash
# ---------------------------------------------------------------------------

def _hash64(value: int, seed: int) -> int:
    """64-bit hash matching Rust implementation."""
    x = (value ^ seed) & _MASK64
    x = ((x ^ (x >> 30)) * _HASH_SEED_B) & _MASK64
    x = ((x ^ (x >> 27)) * _HASH_SEED_C) & _MASK64
    x = (x ^ (x >> 31)) & _MASK64
    return x


def _shingle_hash(s: str) -> int:
    """Hash a shingle string to a 64-bit integer."""
    h = 0
    for c in s:
        h = ((h * 31) + ord(c)) & _MASK64
    return h


def compute_minhash(shingles: list[str], num_hashes: int = 128) -> list[int]:
    """Compute MinHash signature from shingles."""
    if not shingles:
        return [_MASK64] * num_hashes

    shingle_hashes = [_shingle_hash(s) for s in shingles]
    signature = []

    for i in range(num_hashes):
        seed = (_HASH_SEED_A * (i + 1)) & _MASK64
        min_hash = min((_hash64(h, seed) for h in shingle_hashes), default=_MASK64)
        signature.append(min_hash)

    return signature


def minhash_similarity(sig1: list[int], sig2: list[int]) -> float:
    """Compute Jaccard similarity estimate from two MinHash signatures."""
    if len(sig1) != len(sig2) or not sig1:
        return 0.0
    matching = sum(1 for a, b in zip(sig1, sig2) if a == b)
    return matching / len(sig1)


# ---------------------------------------------------------------------------
# LSH Banding
# ---------------------------------------------------------------------------

def lsh_candidates(
    signatures: list[tuple[int, list[int]]],  # (chunk_index, signature)
    num_bands: int = 16,
) -> set[tuple[int, int]]:
    """Find candidate pairs using LSH banding.

    Signatures are split into bands; chunks sharing a band bucket are candidates.
    """
    if not signatures or not signatures[0][1]:
        return set()

    num_hashes = len(signatures[0][1])
    rows_per_band = num_hashes // num_bands

    candidates: set[tuple[int, int]] = set()

    for band_idx in range(num_bands):
        start = band_idx * rows_per_band
        end = start + rows_per_band
        buckets: dict[int, list[int]] = defaultdict(list)

        for chunk_idx, sig in signatures:
            band_hash = hash(tuple(sig[start:end]))
            bucket = buckets[band_hash]
            for other_idx in bucket:
                pair = (min(chunk_idx, other_idx), max(chunk_idx, other_idx))
                candidates.add(pair)
            bucket.append(chunk_idx)

    return candidates


# ---------------------------------------------------------------------------
# UnionFind for clustering
# ---------------------------------------------------------------------------

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def _prepare_signatures(
    chunks: list[CodeChunk], config: DuplicationConfig,
) -> tuple[list[tuple[int, CodeChunk]], list[tuple[int, list[int]]]]:
    """Filter chunks, normalize, compute MinHash signatures."""
    filtered = [
        (i, c) for i, c in enumerate(chunks)
        if c.source.count("\n") + 1 >= config.min_lines
    ]
    if not filtered:
        return [], []

    normalized = [normalize_code(c.source) for _, c in filtered]
    sigs = [
        (i, compute_minhash(shingle(n), config.num_hashes))
        for i, n in enumerate(normalized)
    ]
    return filtered, sigs


def _verify_candidates(
    candidates, signatures, min_similarity, num_chunks: int,
) -> tuple[UnionFind, dict[tuple[int, int], float]]:
    """Verify LSH candidates and build UnionFind."""
    uf = UnionFind(num_chunks)
    pair_sims: dict[tuple[int, int], float] = {}
    for idx1, idx2 in candidates:
        sim = minhash_similarity(signatures[idx1][1], signatures[idx2][1])
        if sim >= min_similarity:
            uf.union(idx1, idx2)
            pair_sims[(idx1, idx2)] = sim
    return uf, pair_sims


def _build_clusters(
    filtered, uf, pair_sims,
) -> list[DuplicateCluster]:
    """Build DuplicateClusters from UnionFind groups."""
    clusters_map: dict[int, list[int]] = defaultdict(list)
    for i in range(len(filtered)):
        clusters_map[uf.find(i)].append(i)

    clusters: list[DuplicateCluster] = []
    for indices in clusters_map.values():
        if len(indices) < 2:
            continue
        cluster_chunks = [filtered[i][1] for i in indices]
        sims = [
            pair_sims.get((min(a, b), max(a, b)), 0.0)
            for a in indices for b in indices if a < b
        ]
        avg_sim = sum(sims) / len(sims) if sims else 0.0
        clusters.append(DuplicateCluster(chunks=cluster_chunks, similarity=avg_sim))
    return clusters


def find_duplicates(
    chunks: list[CodeChunk],
    config: DuplicationConfig | None = None,
) -> list[DuplicateCluster]:
    """Find clusters of duplicated code chunks."""
    config = config or DuplicationConfig()
    filtered, signatures = _prepare_signatures(chunks, config)
    if not filtered:
        return []
    candidates = lsh_candidates(signatures, config.num_bands)
    uf, pair_sims = _verify_candidates(candidates, signatures, config.min_similarity, len(filtered))
    return _build_clusters(filtered, uf, pair_sims)


def find_duplicate_pairs(
    chunks: list[CodeChunk],
    config: DuplicationConfig | None = None,
) -> list[DuplicatePair]:
    """Find raw duplicate pairs (for `dry` command)."""
    config = config or DuplicationConfig()
    filtered, signatures = _prepare_signatures(chunks, config)
    if not filtered:
        return []
    candidates = lsh_candidates(signatures, config.num_bands)
    pairs: list[DuplicatePair] = []
    for idx1, idx2 in candidates:
        sim = minhash_similarity(signatures[idx1][1], signatures[idx2][1])
        if sim >= config.min_similarity:
            pairs.append(DuplicatePair(
                chunk1=filtered[idx1][1],
                chunk2=filtered[idx2][1],
                similarity=sim,
            ))
    return pairs
