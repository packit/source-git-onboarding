# source-git-onboarding

Automate onboarding with https://github.com/packit/dist-git-to-source-git

## Configure

For `PAGURE_TOKEN` & `GITLAB_TOKEN` see `secrets/stg/packit-service.yaml` in our private repo.

Don't forget to `sudo setenforce 0` otherwise mock fails with
`/bin/mount -n -t tmpfs -o rprivate tmpfs /var/lib/mock/centos-stream-x86_64-bootstrap/root/proc`

## Run

List of packages to be onboarded is in [onboard/input/input-pkgs.yml](onboard/input/input-pkgs.yml).

```
For each package:
    clone rpm (dist-git) repo
    clone source-git repo if exists
    check spec file for setup/autosetup/conditional patch
    Dist2Src.convert()
    create srpm & mock build
    write result to onboard/input/result.yml
    if mock build succeeded:
      create source-git project/repo if not cloned previously
      push source-git repo
```

If you want to skip the mock build part, set `SKIP_BUILD` to any value, e.g.
`SKIP_BUILD=yes make run-onboard`.
This is useful if you want to onboard a package which has some minor build issue, like

- missing build dependency
- some failing test(s)

If you prove that it behaves the same even with the package being added to
[VERY_VERY_HARD_PACKAGES](https://github.com/packit/dist-git-to-source-git/blob/master/dist2src/constants.py#L12)
then it should be OK to onboard such package.

If you want to [update](https://github.com/packit/dist-git-to-source-git/pull/45)
already existing branch in a source-git repo, put your package:branch into
[onboard/input/update-pkgs.yml](onboard/input/update-pkgs.yml)
and run `UPDATE=yes make run-onboard`.
