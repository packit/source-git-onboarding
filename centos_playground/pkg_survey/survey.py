import os
import re
import requests
import subprocess
import shutil
import sys
import yaml

from click.testing import CliRunner
# I am too lazy to make this not shitty (no one other will ever use this script anyway :D ),
# but if you really want to use this thing, you know what to do
sys.path.insert(1, '/home/dhodovsk/repos/github.com/packit-service/dist-git-to-source-git')
from dist2src.cli import convert
from git import Repo
from packit.config import Config
from packit.cli.utils import get_packit_api
from packit.local_project import LocalProject

work_dir = '/tmp/playground'
result = []
packit_conf = Config.get_user_config()
runner = CliRunner()
BRANCH = "c8"


class CentosPackageSurvey:
    def __init__(self, project_info):
        self.project_info = project_info
        self.src_dir = ""
        self.rpm_dir = ""
        self.pkg_res = {}
        self.srpm_path = ""

    def clone(self):
        git_url = f"https://git.centos.org/{self.project_info['fullname']}"
        try:
            Repo.clone_from(git_url, f"{work_dir}/rpms/{self.project_info['name']}", branch=BRANCH)
            return True
        except Exception as ex:
            if f'Remote branch {BRANCH} not found' in str(ex):
                return False
            self.pkg_res["package_name"] = self.project_info['name']
            self.pkg_res['error'] = f"CloneError: {ex}"
            return False

    def run_srpm(self):
        try:
            packit_api = get_packit_api(config=packit_conf, local_project=LocalProject(Repo(self.src_dir)))
            self.srpm_path = packit_api.create_srpm(srpm_dir=self.src_dir)
        except Exception as e:
            self.pkg_res['error'] = f"SRPMError: {e}"

    def convert(self):
        try:
            runner.invoke(convert,
                          [f"{self.rpm_dir}:{BRANCH}", f"{self.src_dir}:{BRANCH}]"],
                          catch_exceptions=False)
            return True
        except Exception as ex:
            self.pkg_res['error'] = f"ConvertError: {ex}"
            return False

    def cleanup(self):
        if os.path.exists(self.rpm_dir):
            shutil.rmtree(self.rpm_dir)
        if os.path.exists(self.src_dir):
            shutil.rmtree(self.src_dir)

    def do_mock_build(self):
        c = subprocess.run(['mock', '-r', 'centos-stream-x86_64', 'rebuild', self.srpm_path])
        if not c.returncode:
            return
        err_log_file = f"mock_error_builds/{self.project_info['name']}.log"
        shutil.copyfile('/var/lib/mock/centos-stream-x86_64/result/build.log', err_log_file)
        self.pkg_res['error'] = f'mock build failed. More info in: {err_log_file}'

    @staticmethod
    def get_conditional_info(spec_cont):
        conditions = re.findall(r'\n%if.*?\n%endif', spec_cont, re.DOTALL)
        result = []
        p = re.compile("\n%if (.*)\n")
        for con in conditions:
            if '\n%patch' in con:
                found = p.search(con)
                if found:
                    result.append(found.group(1))
        return result

    def run(self):
        if not self.clone():
            return

        self.rpm_dir = f"{work_dir}/rpms/{self.project_info['name']}"
        self.src_dir = f"{work_dir}/src/{self.project_info['name']}"

        self.pkg_res["package_name"] = self.project_info['name']
        specfile_path = f"{self.rpm_dir}/SPECS/{self.project_info['name']}.spec"
        if not os.path.exists(specfile_path):
            self.pkg_res['error'] = 'Specfile not found.'
            self.cleanup()
            return

        with open(specfile_path, "r") as spec:
            spec_cont = spec.read()
            self.pkg_res.update({
                "autosetup": bool(re.search(r'\n%autosetup', spec_cont)),
                "setup": bool(re.search(r'\n%setup', spec_cont)),
                "conditional_patch": self.get_conditional_info(spec_cont),
            })

        if not self.convert():
            self.pkg_res['size_rpms'] = subprocess.check_output(['du', '-s', self.rpm_dir]).split()[0].decode('utf-8')
        else:
            self.run_srpm()
            self.pkg_res['size'] = subprocess.check_output(['du', '-s', self.src_dir]).split()[0].decode('utf-8')
            if self.srpm_path:
                self.do_mock_build()
        self.cleanup()


def fetch_centos_pkgs_info(page):
    i = 0
    while True:
        print(page)
        r = requests.get(page)
        for p in r.json()["projects"]:
            print(f"Processing package: {p['name']}")
            cps = CentosPackageSurvey(p)
            cps.run()
            if cps.pkg_res:
                print(cps.pkg_res)
                result.append(cps.pkg_res)
        page = r.json()["pagination"]["next"]
        if not page:
            break
        i = i+1
        if not (i % 2):
            with open('intermediate-result.yml', 'w') as outfile:
                yaml.dump(result, outfile)


if __name__ == '__main__':
    if not os.path.exists(work_dir):
        print("Your work_dir is missing.")
    if not os.path.exists(f"{work_dir}/rpms"):
        os.mkdir(f"{work_dir}/rpms")
    if not os.path.exists(f"mock_error_builds"):
        os.mkdir(f"mock_error_builds")
    fetch_centos_pkgs_info('https://git.centos.org/api/0/projects?namespace=rpms&owner=centosrcm&short=true')
    with open('result-data.yml', 'w') as outfile:
        yaml.dump(result, outfile)

