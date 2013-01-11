libvirt_utils
=============

kvm_image_adjuster.py:

This is a simple provisioning-helper script for KVM images.
You can clone your VM image by
  1. copy image file and XML definition file, and
  2. run kvm_image_adjuster.py to modify IP address, hostname, etc.

For example, if you are going to set the following parameters to "test.img" and "test.xml":

<dl>
  <dt>eth0</dt>
  <dd>Mac Address: auto generated, IP Address: 10.7.9.100, Netmask: 255.255.0.0</dd>
  <dt>eth1</dt>
  <dd>Mac Address: auto generated, IP Address and Netmask: DHCP</dd>
  <dt>Default Gateway</dt>
  <dd>10.7.9.1</dd>
  <dt>Hostname</dt>
  <dd>vm.example.com</dd>
  <dt>DNS Nameservers</dt>
  <dd>8.8.8.8, 8.8.4.4</dd>
  <dt>DNS Search Domains</dt>
  <dd>dept.example.com, example.com</dd>
</dl>  

Run this script like this:

<pre>
./kvm_image_adjuster.py --image=./test.img --xml=./test.xml \
--interface=eth0/auto/10.7.9.100/255.255.0.0,eth1/auto/dhcp/dhcp \
--primary=eth0 --gateway=10.0.0.1 \
--hostname=vm.example.com \
--nameserver=8.8.8.8,8.8.4.4 \
--domain=dept.example.com,example.com
</pre>

Additionally, if you get the copied VM image to work for serial console (with "virsh console"), use "--serial-console" option.

Notes:

If you use RHEL6 KVM and Ubuntu VM, first copy augeas_lenses/interfaces.aug to /usr/share/augeas/lenses/dist/.
Augeas_lenses/interfaces.aug is a libaugeas lense file for /etc/network/interfaces of Ubuntu.
Kvm_image_adjuster.py uses libguestfs and libaugeas to manipulate several /etc files, but libaugeas in RHEL6 is too old to play with /etc/network/interfaces for Ubuntu.

Tested Environments:
* Hypervisors: RHEL6 KVM
* Guest OSes: RHEL 6.3, Ubuntu 12.04

Prerequisites:
* Packages: python-libguestfs

