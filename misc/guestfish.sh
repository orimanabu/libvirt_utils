#!/bin/sh

if [ x"$#" != x"2" ]; then
	echo "$0 imgpath xmlpath"
	exit 1
fi
imgpath=$1; shift
xmlpath=$1; shift

echo "=> img"
guestfish -a ${imgpath} -i <<END
echo "==> /etc/sysconfig/network-scripts/ifcfg-*"
glob cat /etc/sysconfig/network-scripts/ifcfg-{bond,eth}[0-9]
echo "==> /etc/udev/rules.d/70-persistent-net.rules"
grep 'ATTR{address}' /etc/udev/rules.d/70-persistent-net.rules
echo "==> /etc/sysconfig/network"
cat /etc/sysconfig/network
echo "==> /boot/grub/menu.lst"
cat /boot/grub/menu.lst
echo "==> /etc/init/start-ttys.conf"
tail-n 3 /etc/init/start-ttys.conf
echo "==> /etc/inittab"
tail-n 1 /etc/inittab
END
echo "=> xml"
grep -E '<name>|<source file|<mac' ${xmlpath}
