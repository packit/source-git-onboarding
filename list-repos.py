#!/usr/bin/python3
"""
There is no proper CLI interface here: it's gonna be used only once.

Gitlab token is picked from an env var GITLAB_TOKEN, make sure to set it.
"""
import json
import os
from pathlib import Path
from typing import Iterable, List, Tuple, Dict

import gitlab
import tabulate
from gitlab import GitlabError
from gitlab.v4.objects import Project, Group, ProjectBranch

src_group_prefix = "redhat/centos-stream/src/"
src_group_id = 9376152
# we're not touching kernel's repositories:
# * c8s - we keep it as the kernel team wants to use it
# * c9s - actively being used
# * there are some other repos kernel uses
# kernel_src_group_id = 10873929
gl = gitlab.Gitlab(
    url="https://gitlab.com/", private_token=os.getenv("GITLAB_TOKEN", None)
)
packages_path = Path("./packages.json")


def iterate_group_projects(group: Group) -> Iterable[Project]:
    """yield Project of a Group"""
    page = 0
    while True:
        projects = group.projects.list(lazy=True, page=page)
        if not projects:  # EOF
            break

        for project in projects:
            # project doesn't contain the branches manager,
            # also don't do lazy=True since we need name
            manageable_project = gl.projects.get(project.id)
            yield manageable_project
        page += 1


def transform_to_tabulate(data: Dict[str, Tuple]) -> List[Tuple]:
    """transform provided Dict into a List of Tuple so the data
    can be visualized with tabulate properly"""
    return sorted(
        ((package_name, branches) for package_name, branches in data.items()),
        key=lambda item: item[0],
    )


def collect_projects(c8s_projects: Dict, c9s_projects: Dict, group: Group):
    """Iterate through a provided group and process its projects.
    packages.json is being continuously updated during the loop"""
    for project in iterate_group_projects(group):
        print(f"Project {project.name}")
        if project.name in c9s_projects or project.name in c8s_projects:
            print("> skip >")
            continue
        try:
            branches: List[ProjectBranch] = project.branches.list()
        except GitlabError as e:
            print(f"!!! {project.name}: {e}")
            raise e
        branches_list = [b.name for b in branches]
        if any(b.startswith("c9") for b in branches_list):
            print(f"[ c9 {branches_list}")
            c9s_projects[project.name] = branches_list
        else:
            print(f"[ c8 {branches_list}")
            c8s_projects[project.name] = branches_list
        # We are doing a few thousands HTTP requests here. GitLab API can block, return 500,
        # so we want to efficiently cache the replies on disk
        packages_path.write_text(json.dumps({"c9": c9s_projects, "c8": c8s_projects}))


def display_packages(c9_packages, c8_packages):
    """visualize packages and branches as a pretty table"""
    print(f"## c9 ({len(c9_packages)} packages)")
    print(
        tabulate.tabulate(
            transform_to_tabulate(c9_packages), headers=["Package", "Branches"]
        )
    )
    print(f"\n## c8-only ({len(c8_packages)} packages)")
    print(
        tabulate.tabulate(
            transform_to_tabulate(c8_packages), headers=["Package", "Branches"]
        )
    )


def archive_c8s_projects(c8s_projects: List[str]):
    """set repositories to be archived"""
    for project_name in c8s_projects:
        project = gl.projects.get(src_group_prefix + project_name)
        project.description = (
            "This repository will be removed by the end of March 2022 since it wasn't used "
            "in the past 16 months. [More info]"
            "(https://lists.centos.org/pipermail/centos-devel/2022-February/120222.html)."
        )
        project.save()
        project.archive()
        print(f"Project {project.name} archived.")


def delete_c8s_projects(c8s_projects: List[str]):
    """DELETE repositories"""
    for project_name in c8s_projects:
        project = gl.projects.get(src_group_prefix + project_name)
        project.delete()
        print(f"Project {project.name} DELETED.")


def lock_down_c8_branch(c9s_projects: List[str]):
    """Configure the c8 branch so no one can edit it"""
    for project_name in c9s_projects:
        project = gl.projects.get(src_group_prefix + project_name)
        for branch in project.branches.list():
            if branch.name.startswith("c8"):
                project.protectedbranches.create(
                    {
                        "name": branch.name,
                        # 0 = no one can do that
                        # https://docs.gitlab.com/ee/api/protected_branches.html
                        "merge_access_level": 0,
                        "push_access_level": 0,
                    }
                )
                print(f"Branch {branch.name} of project {project.name} locked down.")


def delete_c8_branches(c9s_projects: List[str]):
    """delete branches that start with c8"""
    for project_name in c9s_projects:
        project = gl.projects.get(src_group_prefix + project_name)
        for branch in project.branches.list():
            if branch.name.startswith("c8"):
                branch.delete()
                print(f"Branch {branch.name} of project {project.name} DELETED.")


def main():
    """
    By default, go through the /src/ group (namespace) and process every project.
    Store info about branches and distinct b/w c8s-only projects and c8s+c9s.
    """
    src_group = gl.groups.get(id=src_group_id)

    c8s_projects: Dict[str, List[str]] = {}
    c9s_projects: Dict[str, List[str]] = {}
    if packages_path.is_file():
        data = json.loads(packages_path.read_text())
        c8s_projects = data.get("c8", {})
        c9s_projects = data.get("c9", {})

    collect_projects(c8s_projects, c9s_projects, src_group)

    display_packages(c9s_projects, c8s_projects)


main()
