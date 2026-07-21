"""Fluent shell command builder supporting ``|`` (pipe) and ``>`` (redirect)."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ramify.core.session import Session
    from ramify.models.result import CommandResult


class Command:
    """A lazily-built shell command bound to a :class:`Session`.

    Examples::

        session.git("status")                    # Command("git status")
        session.ls("-la") | session.grep("py")   # ls -la | grep py
        session.echo("hi") > "out.txt"           # echo hi > out.txt

    Call :meth:`exec` (or pass to ``session.run``) to execute.
    """

    def __init__(self, session: Session, text: str) -> None:
        self._session = session
        self.text = text

    def __call__(self, *args: str) -> Command:
        parts = [self.text, *(shlex.quote(str(a)) for a in args)]
        return Command(self._session, " ".join(parts))

    def __or__(self, other: Command | str) -> Command:
        rhs = other.text if isinstance(other, Command) else other
        return Command(self._session, f"{self.text} | {rhs}")

    def __gt__(self, target: str) -> Command:
        return Command(self._session, f"{self.text} > {shlex.quote(target)}")

    def __rshift__(self, target: str) -> Command:
        return Command(self._session, f"{self.text} >> {shlex.quote(target)}")

    def exec(self) -> CommandResult:
        return self._session.run(self.text)

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"Command({self.text!r})"
