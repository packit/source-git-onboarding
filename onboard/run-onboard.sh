#!/usr/bin/bash

mkdir --mode=0700 -p "${HOME}/.ssh"

pushd "${HOME}/.ssh"
install -m 0600 /my-ssh/id_rsa .
install -m 0644 /my-ssh/id_rsa.pub .

eval $(ssh-agent -s)
ssh-add id_rsa
ssh-add -l

ssh-keyscan git.stg.centos.org >>known_hosts
ssh-keyscan gitlab.com >>known_hosts
popd

# debugging
# export GIT_SSH_COMMAND="ssh -vvv"

python3 onboard.py
