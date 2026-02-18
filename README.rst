SpacemiT K3 gadget
==================

Install dependencies
--------------------

.. code-block:: bash

    sudo apt-get update
    sudo apt-get install git snapd qemu-user-static ubuntu-dev-tools
    sudo snap install --classic ubuntu-image

Build image
-----------

.. code-block:: bash

    sudo ubuntu-image --debug classic image-definition.yaml

For debugging add --workdir /tmp/workdir.

First boot
----------

Login with user ubuntu, password ubuntu.
