import re
import shutil
import subprocess
from logging import getLogger
from pathlib import Path
from typing import Dict, Any, Optional

import git
import requests
import yaml
from click.testing import CliRunner
from dist2src.core import Dist2Src

from packit.api import PackitAPI
from packit.cli.utils import get_packit_api
from packit.config import Config
from packit.local_project import LocalProject

logger = getLogger(__name__)

work_dir = Path("/tmp/playground")
rpms_path = work_dir / "rpms"
result = []
packit_conf = Config.get_user_config()
runner = CliRunner()

BRANCH = "c8s"


class CentosPkgValidatedConvert:
    def __init__(self, project_info, distgit_branch: str):
        self.project_info = project_info
        self.src_dir: Optional[Path] = None
        self.rpm_dir: Optional[Path] = None
        self.result: Dict[str, Any] = {}
        self.packit_api: Optional[PackitAPI] = None
        self.srpm_path = ""
        self.distgit_branch = distgit_branch
        self.d2s: Optional[Dist2Src] = None

    def clone(self):
        git_url = f"https://git.centos.org/{self.project_info['fullname']}"
        try:
            git.Git(rpms_path).clone(git_url)
            r = git.Repo(rpms_path / self.project_info["name"])
            r.git.checkout(self.distgit_branch)
            return True
        except Exception as ex:
            if f"Remote branch {self.distgit_branch} not found" in str(ex):
                return False
            self.result["package_name"] = self.project_info["name"]
            self.result["error"] = f"CloneError: {ex}"
            return False

    def run_srpm(self):
        try:
            self.packit_api = get_packit_api(
                config=packit_conf, local_project=LocalProject(git.Repo(self.src_dir))
            )
            self.srpm_path = self.packit_api.create_srpm(srpm_dir=self.src_dir)
        except Exception as e:
            self.result["error"] = f"SRPMError: {e}"

    def convert(self):
        try:
            self.d2s = Dist2Src(
                dist_git_path=self.rpm_dir,
                source_git_path=self.src_dir,
            )
            self.d2s.convert(self.distgit_branch, self.distgit_branch)
            return True
        except Exception as ex:
            self.result["error"] = f"ConvertError: {ex}"
            return False

    def cleanup(self):
        if self.rpm_dir.is_dir():
            shutil.rmtree(self.rpm_dir)
        if self.src_dir.is_dir():
            shutil.rmtree(self.src_dir)

    def do_mock_build(self):
        c = subprocess.run(
            ["mock", "-r", "centos-stream-x86_64", "rebuild", self.srpm_path]
        )
        if not c.returncode:
            return
        self.result["error"] = "mock build failed"

    @staticmethod
    def get_conditional_info(spec_cont):
        conditions = re.findall(r"\n%if.*?\n%endif", spec_cont, re.DOTALL)
        result = []
        p = re.compile("\n%if (.*)\n")
        for con in conditions:
            if "\n%patch" in con:
                found = p.search(con)
                if found:
                    result.append(found.group(1))
        return result

    def run(self, cleanup=False, skip_build=False):
        if not self.clone():
            return

        self.rpm_dir = rpms_path / self.project_info["name"]
        self.src_dir = work_dir / "src" / self.project_info["name"]

        self.result["package_name"] = self.project_info["name"]
        specfile_path = self.rpm_dir / "SPECS" / f"{self.project_info['name']}.spec"
        if not specfile_path.is_file():
            self.result["error"] = "Specfile not found."
            self.cleanup()
            return

        with specfile_path.open() as spec:
            spec_cont = spec.read()
            self.result.update(
                {
                    "autosetup": bool(re.search(r"\n%autosetup", spec_cont)),
                    "setup": bool(re.search(r"\n%setup", spec_cont)),
                    "conditional_patch": self.get_conditional_info(spec_cont),
                }
            )

        if self.convert():
            self.run_srpm()
            self.result["size"] = (
                subprocess.check_output(["du", "-s", self.src_dir])
                .split()[0]
                .decode("utf-8")
            )
            if self.srpm_path and not skip_build:
                self.do_mock_build()
        else:
            self.result["size_rpms"] = (
                subprocess.check_output(["du", "-s", self.rpm_dir])
                .split()[0]
                .decode("utf-8")
            )
        if cleanup:
            self.cleanup()


def fetch_centos_pkgs_info(page):
    i = 0
    while True:
        logger.info(page)
        r = requests.get(page)
        for p in r.json()["projects"]:
            logger.info(f"Processing package: {p['name']}")
            converter = CentosPkgValidatedConvert(p, BRANCH)
            converter.run(cleanup=True)
            if converter.result:
                logger.info(converter.result)
                result.append(converter.result)
        page = r.json()["pagination"]["next"]
        if not page:
            break
        i += 1
        if not (i % 2):
            with open("intermediate-result.yml", "w") as outfile:
                yaml.dump(result, outfile)


if __name__ == "__main__":
    if not work_dir.is_dir():
        logger.warning("Your work_dir is missing.")
    rpms_path.mkdir(exist_ok=True)
    Path("mock_error_builds").mkdir(exist_ok=True)
    fetch_centos_pkgs_info(
        "https://git.centos.org/api/0/projects?namespace=rpms&owner=centosrcm&short=true"
    )
    with open("result-data.yml", "w") as outfile:
        yaml.dump(result, outfile)
