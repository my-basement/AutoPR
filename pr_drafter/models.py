from typing import List, ClassVar

import pydantic


class RailModel(pydantic.BaseModel):
    rail_spec: ClassVar[str] = ...


class Commit(RailModel):
    rail_spec = """<object name="commit">
<string
    name="message"
    description="The commit message, describing the changes."
    required="true"
    format="length: 5 72"
    on-fail-length="noop"
/>
<string
    name="diff"
    description="The git diff between this commit and the previous, without the index line, able to be applied with `git apply`."
    required="true"
    format="patch"
    on-fail-patch="fix"
/>
</object>"""

    message: str
    diff: str


class PullRequest(RailModel):
    rail_spec = f"""<object name="pull_request">
<string
    name="title"
    description="The title of the pull request."
    required="true"
    format="length: 10 200"
    on-fail-length="noop"
/>
<string
    name="initial_message"
    description="The body of the initial post of the pull request. Should include a description of the changes in pseudocode, and a link to the issue."
    required="true"
    format="length: 10 2000"
/>
<list name="commits" required="true" filter="length 1">
{Commit.rail_spec}
</list>
</object>"""

    title: str
    initial_message: str
    commits: List[Commit]
