import os
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

import config
from ..logging import LOGGER
from .install import install_req  # assuming this is where install_req lives

def git():
    if not os.path.exists(".git"):
        LOGGER(__name__).info("Skipping git setup: .git directory not found.")
        return

    REPO_LINK = config.UPSTREAM_REPO
    if config.GIT_TOKEN:
        GIT_USERNAME = REPO_LINK.split("com/")[1].split("/")[0]
        TEMP_REPO = REPO_LINK.split("https://")[1]
        UPSTREAM_REPO = f"https://{GIT_USERNAME}:{config.GIT_TOKEN}@{TEMP_REPO}"
    else:
        UPSTREAM_REPO = config.UPSTREAM_REPO

    try:
        repo = Repo()
        LOGGER(__name__).info("Git client found [VPS DEPLOYER]")
    except (GitCommandError, InvalidGitRepositoryError):
        try:
            repo = Repo.init()
            origin = repo.create_remote("origin", UPSTREAM_REPO)
            origin.fetch()

            if config.UPSTREAM_BRANCH in origin.refs:
                repo.create_head(
                    config.UPSTREAM_BRANCH,
                    origin.refs[config.UPSTREAM_BRANCH],
                )
                repo.heads[config.UPSTREAM_BRANCH].set_tracking_branch(
                    origin.refs[config.UPSTREAM_BRANCH]
                )
                repo.heads[config.UPSTREAM_BRANCH].checkout(True)
            else:
                LOGGER(__name__).error(f"Branch '{config.UPSTREAM_BRANCH}' not found in upstream.")
                return

            nrs = repo.remote("origin")
            nrs.fetch(config.UPSTREAM_BRANCH)
            try:
                nrs.pull(config.UPSTREAM_BRANCH)
            except GitCommandError:
                repo.git.reset("--hard", "FETCH_HEAD")

            install_req("pip3 install --no-cache-dir -r requirements.txt")
            LOGGER(__name__).info("Fetched updates from upstream repository.")
        except Exception as e:
            LOGGER(__name__).error(f"Git setup failed: {e}")
