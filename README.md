libvirt_utils
=============

utility scripts for libvirt

kvm_image_adjuster.py:
This is a simple provisioning-helper script for KVM images.
You can clone your VM image by
  1. copy image file and XML definition file, and
  2. run kvm_image_adjuster.py to modify IP address, hostname, etc.

If you are going to set the following parameters to test.img and test.xml:
    eth0: Mac Address: auto generated
          IP Address: 10.7.9.100
          Netmask: 255.255.0.0
    eth1: Mac Address: auto generated
          IP Address: DHCP
    Default Gateway: 10.7.9.1
    Hostname: vm.example.com
    DNS Nameservers: 8.8.8.8, 8.8.4.4
    DNS Search Domains: dept.example.com, example.com

Run this script like this:
./kvm_image_adjuster.py --image=./test.img --xml=./test.xml \\
--interface=eth0/auto/10.7.9.100/255.255.0.0,eth1/auto/dhcp/dhcp \\
--primary=eth0 --gateway=10.0.0.1 \\
--hostname=vm.example.com \\
--nameserver=8.8.8.8,8.8.4.4 \\
--domain=dept.example.com,example.com

