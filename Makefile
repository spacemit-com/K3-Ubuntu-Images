image-debug:
	sudo rm -rf workdir
	sudo ubuntu-image --workdir workdir --debug classic \
	image-definition.yaml

image:
	sudo rm -rf workdir
	sudo ubuntu-image --workdir workdir classic image-definition.yaml
