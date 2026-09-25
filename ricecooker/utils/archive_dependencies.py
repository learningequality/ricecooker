"""Move the assets several HTML5 leaves of one package share into one dependency dir.

Kolibri's zipcontent serves one zip per URL, so a leaf reaches a shared asset
only through a relative ``../<dependency>.zip/<path>`` reference. Sharing works in
two steps because that name is the sealed dependency zip's md5:

1. :meth:`SharedAssetExtractor.select` copies each shared asset once into a
   dependency dir, straight from the package.
2. After the caller seals that dir, it stages each leaf's other members and
   :meth:`SharedAssetExtractor.rewrite` points them at the dependency zip.

An asset moves only if the reference mappers rewrote every reference to it, so a
member that only scripts load stays in its leaf.
"""

import os
import posixpath
import shutil
from collections import defaultdict
from urllib.parse import quote

from ricecooker.utils.imscp import contained_path
from ricecooker.utils.references import HTMLMapper
from ricecooker.utils.references import mapper_for
from ricecooker.utils.references import resolve_reference
from ricecooker.utils.references import split_reference
from ricecooker.utils.storage import get_hash


def _map_file(path, member, fn):
    """Apply ``fn`` to every reference in ``path``; write back only on change."""
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    rewritten, _urls = mapper_for(member).map(content, fn)
    if rewritten != content:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(rewritten)


class _Unreadable(Exception):
    """A mapped member can't be read as UTF-8, so rewriting it would corrupt it."""


class _Leaf:
    """One leaf's member md5s and the local refs its mapped members make."""

    def __init__(self, package, members, entry, md5s):
        self.md5s = {member: md5s(member) for member in members}
        self.entry_md5 = self.md5s.get(entry)
        self.pages = set()
        # Mapped member -> the member each local ref names, None when it names none.
        self.targets = {}
        for member in self.md5s:
            mapper = mapper_for(member)
            if mapper is None:
                continue
            paths = package.references(member)
            if paths is None:
                raise _Unreadable(member)
            if isinstance(mapper, HTMLMapper):
                self.pages.add(member)
            self.targets[member] = [
                path if path in self.md5s else None for path in paths
            ]
        self.referenced = {
            target
            for targets in self.targets.values()
            for target in targets
            if target is not None
        }


class SharedAssetExtractor:
    """Extracts the assets ``package``'s leaves share: key -> ``(members, entry)``, in order.

    ``members`` is the leaf's full closure within the package.
    """

    def __init__(self, package, leaves):
        self.package = package
        hashes = {}

        def md5s(member):
            if member not in hashes:
                hashes[member] = get_hash(self._path(member))
            return hashes[member]

        self.leaves = {}
        for key, (members, entry) in leaves.items():
            try:
                self.leaves[key] = _Leaf(package, members, entry, md5s)
            except (OSError, _Unreadable):
                continue
        # Moved md5 -> ``(leaf, member)`` of its first sighting; ``member`` is
        # its path in the dependency dir.
        self.moved = {}

    def select(self, dep_dir):
        """Copy the shared assets into ``dep_dir``; False when nothing is shared."""
        candidates = self._candidates()
        named = self._named()
        while True:
            candidates = self._close(candidates, named)
            self.moved, conflicts = self._place(candidates)
            if not conflicts:
                break
            candidates -= conflicts
        for leaf, member in self.moved.values():
            dest = contained_path(dep_dir, member)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(self._path(member), dest)
            if member in leaf.targets:
                self._relocate(leaf, member, dest)
        return bool(self.moved)

    def shared(self, key):
        """The members of leaf ``key`` the dependency dir now holds."""
        leaf = self.leaves.get(key)
        if leaf is None:
            return set()
        return {m for m in leaf.referenced if leaf.md5s[m] in self.moved}

    def rewrite(self, key, directory, paths, dep_name):
        """Point leaf ``key``'s refs at ``dep_name``; True when any now reference it.

        ``paths`` maps each member staged into ``directory`` to its path there,
        which is its path in the sealed leaf zip.
        """
        moved = self.shared(key)
        leaf = self.leaves.get(key)
        rewritten = False
        for member, path in paths.items():
            if not moved or moved.isdisjoint(leaf.targets.get(member, ())):
                continue
            prefix = "../" * (path.count("/") + 1) + dep_name + "/"

            def to_dependency(ref, member=member, prefix=prefix):
                target = resolve_reference(member, ref)
                if target not in moved:
                    return ref
                _source, dep_path = self.moved[leaf.md5s[target]]
                return prefix + quote(dep_path) + split_reference(ref)[1]

            _map_file(contained_path(directory, path), member, to_dependency)
            rewritten = True
        return rewritten

    def _path(self, member):
        return contained_path(self.package.directory, member)

    def _candidates(self):
        """md5s every holding leaf references, held by two or more leaves."""
        holders = defaultdict(set)
        excluded = set()
        referenced = {}
        for key, leaf in self.leaves.items():
            referenced[key] = {leaf.md5s[member] for member in leaf.referenced}
            # A moved page would resolve its unmapped <a href>/<iframe src>
            # links against the dependency zip.
            excluded |= {leaf.entry_md5} | {leaf.md5s[page] for page in leaf.pages}
            for md5 in leaf.md5s.values():
                holders[md5].add(key)
        return {
            md5
            for md5, keys in holders.items()
            if len(keys) > 1
            and md5 not in excluded
            and all(md5 in referenced[key] for key in keys)
        }

    def _named(self):
        """md5 -> per-ref sets of the md5s its referenced copies name (None: no member)."""
        named = defaultdict(lambda: defaultdict(set))
        for leaf in self.leaves.values():
            for member in leaf.referenced & leaf.targets.keys():
                for i, target in enumerate(leaf.targets[member]):
                    named[leaf.md5s[member]][i].add(leaf.md5s.get(target))
        return named

    @staticmethod
    def _close(candidates, named):
        """Drop mapped candidates whose refs don't all name one candidate each."""
        candidates = set(candidates)
        changed = True
        while changed:
            changed = False
            for md5 in candidates & named.keys():
                refs = named[md5].values()
                if any(len(md5s) > 1 or not md5s <= candidates for md5s in refs):
                    candidates.discard(md5)
                    changed = True
        return candidates

    def _place(self, candidates):
        """``(moved, conflicts)``: each candidate fixed at its first sighting, and the md5s whose path was taken."""
        moved = {}
        taken = set()
        taken_dirs = set()
        conflicts = set()
        for leaf in self.leaves.values():
            for member in sorted(leaf.referenced):
                md5 = leaf.md5s[member]
                if md5 not in candidates or md5 in moved or md5 in conflicts:
                    continue
                # Case-folded, so paths can't collide on a case-insensitive filesystem.
                path = member.casefold()
                parts = path.split("/")
                dirs = {"/".join(parts[:i]) for i in range(1, len(parts))}
                if path in taken or path in taken_dirs or not dirs.isdisjoint(taken):
                    conflicts.add(md5)
                    continue
                taken.add(path)
                taken_dirs |= dirs
                moved[md5] = (leaf, member)
        return moved, conflicts

    def _relocate(self, leaf, member, dest):
        """Re-aim a moved file's refs at the paths their targets moved to."""
        base = posixpath.dirname(member) or "."

        def to_canonical(ref):
            target = resolve_reference(member, ref)
            if target not in leaf.md5s:
                return ref
            _source, path = self.moved[leaf.md5s[target]]
            return quote(posixpath.relpath(path, base)) + split_reference(ref)[1]

        _map_file(dest, member, to_canonical)
