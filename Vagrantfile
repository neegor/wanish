# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "ubuntu/trusty32"
  config.vm.box_url = "https://vagrantcloud.com/ubuntu/boxes/trusty32"
  config.vm.provision :shell, :path => "bootstrap.sh"
end

