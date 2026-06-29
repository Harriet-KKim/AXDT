"""네이밍 — SoT 규칙 ``rule-branch-worktree-naming`` 을 코드로 강제.

단일 식별자 ``w<n>.t<n>-<slug>`` 가 branch·worktree dir·container를 모두 구동한다.
선행 0 금지, 점 구분, 슬래시 금지, slug는 lowercase kebab-case.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

__all__ = [
    "NamingError",
    "Identifier",
    "parse",
    "is_valid",
    "validate",
    "branch",
    "container",
    "worktree_dir",
    "tmux_window",
]

# 선행 0 금지([1-9]\d*), 점 구분, slug는 lowercase kebab(연속/말단 dash 불가).
_RE = re.compile(
    r"^w(?P<wave>[1-9]\d*)\.t(?P<task>[1-9]\d*)-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)

_CONTAINER_PREFIX = "axdt-"
_WORKTREES_ROOT = "worktrees"


class NamingError(ValueError):
    """식별자/이름이 SoT 네이밍 규칙을 위반."""


@dataclass(frozen=True)
class Identifier:
    """한 작업 단위(wave의 task 하나 = Leader = worktree = container)의 식별자."""

    wave: int
    task: int
    slug: str

    def __post_init__(self) -> None:
        # 직접 생성한 경우에도 불변식을 보장한다(렌더가 parse를 우회 못하도록).
        validate(self.value)

    @property
    def value(self) -> str:
        return f"w{self.wave}.t{self.task}-{self.slug}"


def parse(value: str) -> Identifier:
    """식별자 문자열을 파싱한다. 위반 시 :class:`NamingError`."""
    m = _RE.match(value)
    if m is None:
        raise NamingError(f"잘못된 식별자: {value!r} (형식 w<n>.t<n>-<slug>)")
    return Identifier(
        wave=int(m.group("wave")),
        task=int(m.group("task")),
        slug=m.group("slug"),
    )


def is_valid(value: str) -> bool:
    return _RE.match(value) is not None


def validate(identifier: str) -> None:
    """raw 식별자를 검증한다(렌더된 container/worktree 이름이 아님). 위반 시 NamingError."""
    if not is_valid(identifier):
        raise NamingError(f"잘못된 식별자: {identifier!r} (형식 w<n>.t<n>-<slug>)")


def branch(i: Identifier) -> str:
    return i.value


def container(i: Identifier) -> str:
    return f"{_CONTAINER_PREFIX}{i.value}"


def worktree_dir(i: Identifier) -> Path:
    return Path(_WORKTREES_ROOT) / i.value


def tmux_window(i: Identifier) -> str:
    return i.value


# kind 인자를 받는 옛 시그니처 호환을 위한 헬퍼는 두지 않는다(§3: raw 식별자만 검증).
_Kind = Literal["identifier", "branch", "container", "worktree"]  # 문서/참고용
