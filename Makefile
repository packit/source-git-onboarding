build-onboard:
	podman build . -t centos-onboard -f onboard/Containerfile

run-onboard:
	podman run --rm -ti --cap-add=SYS_ADMIN \
	-v ${HOME}/.ssh:/my-ssh:ro,Z \
	-v ${PWD}/onboard/input:/in:rw,Z \
	-v ${PWD}/onboard/onboard.py:/workdir/onboard.py:ro,Z \
	-v ${PWD}/pkg_survey/survey.py:/workdir/survey.py:ro,Z \
	-e PAGURE_TOKEN=${PAGURE_TOKEN} \
	-e GITLAB_TOKEN=${GITLAB_TOKEN} \
	-e DISTGIT_TOKEN=${DISTGIT_TOKEN} \
	-e SKIP_BUILD=${SKIP_BUILD} \
	-e UPDATE=${UPDATE} \
	centos-onboard
