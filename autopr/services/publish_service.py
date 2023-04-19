from typing import Optional

import requests

from autopr.models.artifacts import Issue
from autopr.models.rail_objects import PullRequestDescription, CommitPlan

import structlog

from autopr.services.commit_service import CommitService

log = structlog.get_logger()


class PublishService:
    def __init__(
        self,
        issue: Issue,
        commit_service: CommitService,
    ):
        self.issue = issue
        self.commit_service = commit_service

        self.pr_desc: PullRequestDescription = self._create_placeholder(issue)
        self.progress_updates = []

    def _create_placeholder(self, issue: Issue) -> PullRequestDescription:
        empty_commit = CommitPlan(
            commit_message="[empty] Running...",
        )
        self.commit_service.commit(empty_commit)
        placeholder_pr_desc = PullRequestDescription(
            title=f"Fix #{issue.number}: {issue.title}",
            body="",
            commits=[empty_commit],
        )
        return placeholder_pr_desc

    def publish_call(
        self,
        summary: str,
        default_open=('response',),
        **kwargs
    ):
        subsections = []
        for k, v in kwargs.items():
            # Cast keys to title case
            title = k.title()
            title = title.replace("_", " ")

            # Prefix content with quotation marks
            content = '\n'.join([f"> {line}" for line in v.splitlines()])

            # Construct subsection
            subsection = f"""<details{" open" if k in default_open else ""}>
<summary>{title}</summary>

{content}
</details>"""
            subsections.append(subsection)

        # Concatenate subsections
        subsections_content = '\n\n'.join(subsections)

        # Prefix them with a quotation mark
        subsections_content = '\n'.join([f"> {line}" for line in subsections_content.splitlines()])

        # Construct progress string
        progress_str = f"""<details>
<summary>{summary}</summary>

{subsections_content}

</details>
"""
        self.publish_update(progress_str)

    def set_pr_description(self, pr: PullRequestDescription):
        self.pr_desc = pr
        self.update()

    def publish_update(self, text: str):
        self.progress_updates.append(text)
        self.update()

    def _build_progress_updates(self):
        if not self.progress_updates:
            return ""
        body = "# Progress updates\n"
        for update in self.progress_updates:
            body += f"\n{update}"
        return body

    def _build_body(self, finalize: bool = False):
        body = f"Fixes #{self.issue.number}\n\n"
        body += self.pr_desc.body
        progress = self._build_progress_updates()
        if finalize:
            progress = f"""<details>
  <summary>Click to see progress updates</summary>

  {progress}
</details>
"""
        body += progress
        return body

    def update(self):
        body = self._build_body()
        title = self.pr_desc.title
        self._publish(title, body)

    def finalize(self):
        body = self._build_body(finalize=True)
        title = self.pr_desc.title
        self._publish(title, body)

    def _publish(
        self,
        title: str,
        body: str
    ):
        raise NotImplementedError


class GithubPublishService(PublishService):
    def __init__(
        self,
        issue: Issue,
        commit_service: CommitService,
        token: str,
        owner: str,
        repo_name: str,
        head_branch: str,
        base_branch: str
    ):
        super().__init__(issue, commit_service)
        self.token = token
        self.owner = owner
        self.repo = repo_name
        self.head_branch = head_branch
        self.base_branch = base_branch

    def _get_headers(self):
        return {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }

    def _publish(self, title: str, body: str):
        existing_pr = self._find_existing_pr()
        if existing_pr:
            self._update(title, body)
        else:
            self._create_pr(title, body)

    def _create_pr(self, title: str, body: str):
        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/pulls'
        headers = self._get_headers()
        data = {
            'head': self.head_branch,
            'base': self.base_branch,
            'title': title,
            'body': body,
        }
        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 201:
            log.debug('Pull request created successfully', response=response.json())
        else:
            log.debug('Failed to create pull request', response_text=response.text)

    def _update(self, title: str, body: str):
        existing_pr = self._find_existing_pr()
        if not existing_pr:
            log.debug("No existing pull request found to update")
            return

        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{existing_pr["number"]}'
        headers = self._get_headers()
        data = {
            'title': title,
            'body': body,
        }
        response = requests.patch(url, json=data, headers=headers)

        if response.status_code == 200:
            log.debug('Pull request updated successfully', response=response.json())
        else:
            log.debug('Failed to update pull request', response_text=response.text)

    def _find_existing_pr(self):
        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/pulls'
        headers = self._get_headers()
        params = {'state': 'open', 'head': f'{self.owner}:{self.head_branch}', 'base': self.base_branch}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            prs = response.json()
            if prs:
                return prs[0]  # Return the first pull request found
        else:
            log.debug('Failed to get pull requests', response_text=response.text)

        return None
