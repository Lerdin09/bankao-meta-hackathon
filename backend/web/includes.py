"""
Montagem do HTML a partir de partials (server-side includes).

No HTML escreve-se, numa linha própria:

    <!-- @include partials/pages/home.html -->

e esta linha é substituída pelo conteúdo do ficheiro, mantendo a indentação
da diretiva. Os includes podem ser aninhados. Só usa a biblioteca padrão.
"""
import os
import re
from pathlib import Path
from typing import List, Set

_INCLUDE_RE = re.compile(r"^([ \t]*)<!--\s*@include\s+([^\s>]+)\s*-->[ \t]*$", re.MULTILINE)
_MAX_DEPTH = 10


class IncludeError(Exception):
    """Partial em falta, fora da pasta do frontend ou com inclusão circular."""


def _expand(text: str, root: Path, used: Set[Path], stack: List[Path]) -> str:
    if len(stack) > _MAX_DEPTH:
        raise IncludeError("Profundidade máxima de includes excedida: " + " -> ".join(p.name for p in stack))

    def replace(match: "re.Match[str]") -> str:
        indent, rel = match.group(1), match.group(2)
        target = (root / rel).resolve()
        if root not in target.parents:
            raise IncludeError(f"Include fora da pasta do frontend: {rel}")
        if not target.is_file():
            raise IncludeError(f"Partial não encontrado: {rel}")
        if target in stack:
            raise IncludeError("Include circular: " + " -> ".join(p.name for p in stack + [target]))
        used.add(target)
        content = target.read_text(encoding="utf-8").rstrip("\n")
        content = _expand(content, root, used, stack + [target])
        return "\n".join((indent + line) if line.strip() else "" for line in content.split("\n"))

    return _INCLUDE_RE.sub(replace, text)


def render_html(entry: Path, root: Path):
    """Devolve (html_montado, ficheiros_usados) para o ficheiro `entry` dentro de `root`."""
    root = root.resolve()
    entry = entry.resolve()
    used: Set[Path] = {entry}
    html = _expand(entry.read_text(encoding="utf-8"), root, used, [entry])
    return html, used


class CachedPage:
    """Monta a página uma vez e só volta a montar quando algum ficheiro envolvido muda (útil em desenvolvimento)."""

    def __init__(self, entry: Path, root: Path):
        self.entry = Path(entry)
        self.root = Path(root)
        self._html = ""
        self._files: Set[Path] = set()
        self._signature = None

    def _current_signature(self):
        return tuple(sorted((str(p), os.stat(p).st_mtime_ns) for p in self._files if p.exists()))

    def get(self) -> str:
        if self._signature is None or self._signature != self._current_signature():
            self._html, self._files = render_html(self.entry, self.root)
            self._signature = self._current_signature()
        return self._html
