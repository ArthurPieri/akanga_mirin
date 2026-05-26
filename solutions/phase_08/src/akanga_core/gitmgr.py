from __future__ import annotations

import logging
from pathlib import Path

try:
    from git import InvalidGitRepositoryError, Repo
except ImportError:
    # Fallback for environments without GitPython installed
    Repo = None  # type: ignore
    InvalidGitRepositoryError = Exception  # type: ignore

logger = logging.getLogger(__name__)


class GitManager:
    def __init__(self, vault_path: str | Path) -> None:
        """
        Initialize GitManager for the given vault path.
        Uses git.Repo to open the repository.
        """
        self.vault_path = Path(vault_path).absolute()
        self.repo: Repo | None = None
        if Repo:
            try:
                self.repo = Repo(self.vault_path)
            except InvalidGitRepositoryError:
                self.repo = None
            except Exception as e:
                logger.warning("Failed to open git repo at %s: %s", self.vault_path, e)
                self.repo = None

    def ensure_repo(self) -> Repo | None:
        """Init if not exists."""
        if self.repo is None and Repo:
            try:
                self.repo = Repo.init(self.vault_path)
                logger.info("Initialized git repo at %s", self.vault_path)
            except Exception as e:
                logger.error("Failed to initialize git repo at %s: %s", self.vault_path, e)
                return None
        return self.repo

    def stage_and_commit(self, paths: list[str | Path], message: str) -> str | None:
        """
        Stage specific files and commit.
        Includes a simple check to avoid empty commits.
        """
        if not self.repo:
            logger.debug("No git repository available for commit.")
            return None

        if not paths:
            return None

        try:
            # Stage specific files
            # Ensure paths are relative to repo root for git.index.add
            rel_paths = []
            for p in paths:
                p_abs = Path(p).absolute()
                try:
                    if p_abs.is_relative_to(self.vault_path):
                        rel_paths.append(str(p_abs.relative_to(self.vault_path)))
                    else:
                        logger.warning("Path %s is outside of vault root %s", p, self.vault_path)
                except ValueError:
                    logger.warning("Could not determine relative path for %s", p)

            if not rel_paths:
                return None

            self.repo.index.add(rel_paths)

            # Check if index differs from HEAD (to avoid empty commits)
            if not self.repo.is_dirty(index=True, working_tree=False, untracked_files=False):
                # Nothing staged that differs from current HEAD
                return None

            commit = self.repo.index.commit(message)
            logger.info("Committed: %s - %s", commit.hexsha[:7], message)
            return str(commit.hexsha)
        except Exception as e:
            logger.error("Git stage/commit failed: %s", e)
            return None
