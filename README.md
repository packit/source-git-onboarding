# source-git-onboarding

Automate onboarding with https://github.com/packit/dist-git-to-source-git

## Decommissioning

As of Q1 2022, we are planning to decommission all CentOS Stream 8 source-git
branches (`c8s`, `c8`, `c8s-stream-*`) and repositories hosted on
[gitlab.com/redhat/centos-stream/src](https://gitlab.com/redhat/centos-stream/src/).

### Stage 1

1. Identify c8-only repos (see [packages.json](packages.json))

2. Send an email including a link to the list of repositories and branches to be archived and deleted.

3. Stop the d2s update service.

4. Archive the c8s-only repos & update description of a repo stating they will be deleted in a week

(Wait for a week for some feedback)

### Stage 2

4. Delete the c8-only repos

5. Lock down c8\* branches on the rest of the repos: disallow push & merge (except for kernel/centos-stream-8)

(Wait for a week for some feedback)

### Stage 3

6. Delete the rest of the c8\* branches

7. Decommission rest of the related content:

   - This repo
   - d2s repo
   - Clean up Jira tasks
   - Remove credentials
   - Clean up deployment scripts
   - Ask for deletion for the git.centos.org packit user account
   - Archive `packit/packit-service-centosmsg`
   - Go through research topics and archive as needed
   - Drop scraping of the `/metrics` endpoint in internal prometheus
   - Delete the maintain rotating role

8. Announce to the public the changes were done

# Deprecated - how to use this repo

Since we're going to drop the repositories, code in this repo is no longer
relevant. We will archive this repository once the decommissioning is finished.

## Configure

For `PAGURE_TOKEN` & `GITLAB_TOKEN` see `secrets/stg/packit-service.yaml` in our private repo.
For `DISTGIT_TOKEN` see `secrets/prod/packit-service.yaml` in our private repo.

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
