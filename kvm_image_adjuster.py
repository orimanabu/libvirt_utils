#!/usr/bin/env python
# vi: set et sts=4 sw=4 ts=4 :

# usage:
# ./kvm_image_adjuster.py --image=./test.img --xml=./test.xml --interface=eth0/auto/1.0.0.1/255.255.255.255,eth1/auto/dhcp/dhcp,eth2/auto/1.1.1.1/255.255.0.0 --hostname=vm.iscoc.ibm.mgmt --nameserver=8.8.8.8,11.11.11.11 --domain=ibm.com,iscoc.ibm.com --primary=eth0 --gateway=10.0.0.1 --serial-console

import re
import os
import sys
import optparse
import guestfs
import virtinst.util
from pprint import pprint
from lxml import etree

gflags = {'debug':False, 'os':''}
ifcfgs = {}

AUG_SAVE_BACKUP = 1
AUG_SAVE_NEWFILE = 2
AUG_TYPE_CHECK = 4
AUG_NO_STDINC = 8
AUG_SAVE_NOOP = 16
AUG_NO_LOAD = 32

class ifcfg_base:
    def __init__(self, g, ifname):
        print_debug("==> ifcfg_base.__init__(): %s" % ifname)
        self.g = g
        self.ifname = ifname
        self.augpath = None
        self.mac = None
        self.uuid = None
        self.ipaddr = None
        self.netmask = None
        self.bootproto = None
        self.newmac = None
        self.newuuid = None
        self.newipaddr = None
        self.newnetmask = None
        self.newbootproto = None
        self.newdns = None
        self.newdomain = None
        self.newgateway = None
        self.primary = False

    def prepare(self, **d):
        print_debug("==> ifcfg_base.prepare(): %s" % d)
        self.newbootproto = d.get("bootproto")
        self.newmac = d.get("mac")
        self.newuuid = d.get("uuid")
        self.newipaddr = d.get("ipaddr")
        self.newnetmask = d.get("netmask")
        self.newdns = d.get("dns")
        self.newdomain = d.get("domain")
        self.primary = d.get("primary")
        self.newgateway = d.get("gateway")
        self.newdns = d.get("nameserver")
        self.newdomain = d.get("domain")

    def info(self):
        def print_info(label, oldval, newval):
            print "%15s: %s" % (label, oldval),
            if newval: print "=> %s" % newval
            else: print "(not changed)"

        print_debug("==> ifcfg_base.info()")
        print "====> ifconfig for %s (%s)" % (self.ifname, "primary" if self.primary else "not primary")
        print_info("BOOTPROTO", self.bootproto, self.newbootproto)
        print_info("HWADDR", self.mac, self.newmac)
        print_info("IPADDR", self.ipaddr, self.newipaddr)
        print_info("NETMASK", self.netmask, self.newnetmask)
        print_info("UUID", self.uuid, self.newuuid)
        if self.primary:
            print "%15s: %s" % ("nameserver", self.newdns)
            print "%15s: %s" % ("domain", self.newdomain)

class ifcfg_rhel(ifcfg_base):
    def __init__(self, g, ifname):
        print_debug("==> ifcfg_rhel.__init__(): %s" % ifname)
        ifcfg_base.__init__(self, g, ifname)
        self.augpath = "/files/etc/sysconfig/network-scripts/ifcfg-" + self.ifname
        if g.aug_match(self.augpath + "/BOOTPROTO"):
            self.bootproto = g.aug_get(self.augpath + "/BOOTPROTO").replace('"', '')
        if g.aug_match(self.augpath + "/HWADDR"):
            self.mac = g.aug_get(self.augpath + "/HWADDR").replace('"', '').lower()
        if g.aug_match(self.augpath + "/IPADDR"):
            self.ipaddr = g.aug_get(self.augpath + "/IPADDR").replace('"', '')
        if g.aug_match(self.augpath + "/NETMASK"):
            self.netmask = g.aug_get(self.augpath + "/NETMASK").replace('"', '')
        if g.aug_match(self.augpath + "/UUID"):
            self.uuid = g.aug_get(self.augpath + "/UUID").replace('"', '')

    def commit_update(self):
        print_debug("==> ifcfg_rhel.update()")
        g = self.g
        augpath = self.augpath
        path = re.sub('^/files', '', augpath)
        #print " => ifcfg.commit_update()"
        print "====> writing new configuration for %s..." % self.ifname
        print "  - setting " + path
        if self.newbootproto: g.aug_set(augpath + "/BOOTPROTO", '"%s"' % self.newbootproto)
        if self.newmac:       g.aug_set(augpath + "/HWADDR", '"%s"' % self.newmac)
        if self.newipaddr:    g.aug_set(augpath + "/IPADDR", '"%s"' % self.newipaddr)
        if self.newnetmask:   g.aug_set(augpath + "/NETMASK", '"%s"' % self.newnetmask)
        if self.newuuid:      g.aug_set(augpath + "/UUID", '"%s"' % self.newuuid)
        if self.primary and self.newgateway: g.aug_set(augpath + "/GATEWAY", '"%s"' % self.newgateway)
        if self.primary and self.newdns and len(self.newdns) > 0:
            g.aug_set(augpath + "/DNS1", '"%s"' % self.newdns[0])
        if self.primary and self.newdns and len(self.newdns) > 1:
            g.aug_set(augpath + "/DNS2", '"%s"' % self.newdns[1])
        if self.primary and self.newdomain: g.aug_set(augpath + "/DOMAIN", '"%s"' % " ".join(self.newdomain))
        g.aug_set(augpath + "/NM_CONTROLLED", '"no"')
        g.aug_set(augpath + "/ONBOOT", '"yes"')
        g.aug_set(augpath + "/USERCTL", '"no"')
        g.aug_set(augpath + "/PEERDNS", '"no"')
        g.aug_set(augpath + "/IPV6INIT", '"no"')
        g.aug_save()

        print "  - renaming backup files (ifcfg-eth*.augpath => _ifcfg-eth*.augpath)"
        backup_path = path + ".augsave"
        new_backup_path = os.path.dirname(backup_path) + "/_" + os.path.basename(backup_path)
        if g.exists(backup_path):
            g.mv(backup_path, new_backup_path)

        print "  - repairing selinux labels"
        #g.sh("restorecon " + path)
        g.sh("chcon -t net_conf_t " + path)

class ifcfg_ubuntu(ifcfg_base):
    def __init__(self, g, ifname):
        print_debug("==> ifcfg_ubuntu.__init__(): %s" % ifname)
        ifcfg_base.__init__(self, g, ifname)
        if_augpaths = g.aug_match("/files/etc/network/interfaces/iface")
        #print "  if_augpaths:", if_augpaths
        for if_augpath in if_augpaths:
            ifname_aug = g.aug_get(if_augpath)
            #print "  ifname=%s, iface=%s" % (ifname_aug, ifname)
            if ifname_aug == ifname:
                self.augpath = if_augpath
                if g.aug_match(self.augpath + "/method"):  self.bootproto = g.aug_get(self.augpath + "/method")
                if g.aug_match(self.augpath + "/address"): self.ipaddr = g.aug_get(self.augpath + "/address")
                if g.aug_match(self.augpath + "/netmask"): self.netmask = g.aug_get(self.augpath + "/netmask")

    def commit_update(self):
        print_debug("==> ifcfg_ubuntu.commit_update()")
        print "===> writing new configuration for %s..." % self.ifname
        g = self.g
        if not self.augpath:
            g.aug_insert("/files/etc/network/interfaces/auto[last()]", "auto", 0)
            g.aug_set("/files/etc/network/interfaces/auto[last()]/1", self.ifname)
            g.aug_insert("/files/etc/network/interfaces/iface[last()]", "iface", 0)
            g.aug_set("/files/etc/network/interfaces/iface[last()]", self.ifname)
            g.aug_set("/files/etc/network/interfaces/iface[last()]/family", "inet")
            self.augpath = g.aug_match("/files/etc/network/interfaces/iface[last()]")[0]
            print "  - setting %s (not exists, created)" % re.sub("^/files", "", self.augpath)
        else:
            print "  - setting %s (exists)" % re.sub("^/files", "", self.augpath)
        augpath = self.augpath
        if self.newbootproto: g.aug_set(augpath + "/method", self.newbootproto)
        if self.newipaddr:    g.aug_set(augpath + "/address", self.newipaddr)
        if self.newnetmask:   g.aug_set(augpath + "/netmask", self.newnetmask)
        if self.primary and self.newgateway: g.aug_set(augpath + "/gateway", self.newgateway)
        if self.primary and self.newdns:     g.aug_set(augpath + "/dns-nameservers", " ".join(self.newdns))
        if self.primary and self.newdomain:  g.aug_set(augpath + "/dns-search", " ".join(self.newdomain))
        g.aug_save()

def print_debug(str):
    if gflags['debug']:
        print "*** debug ***", str

def compare_pathlen(a, b):
    ret = None
    if len(a[0]) > len(b[0]): ret = 1
    elif len(a[0]) == len(b[0]): ret = 0
    else: ret = -1
    return ret

def parse_interface_option(optstr):
    ifaces = optstr.split(",")
    ret = {}
    for iface in ifaces:
        (name, mac, ipaddr, netmask) = iface.split("/")
        mac = mac.lower()
        ret[name] = {'mac':mac, 'ipaddr':ipaddr, 'netmask':netmask}
    return ret

def generate_new_uuid():
    #return os.popen("uuidgen").read().strip()
    return virtinst.util.uuidToString(virtinst.util.randomUUID())

def generate_new_mac():
    return virtinst.util.randomMAC(type="qemu")

def generate_new_macs(defined_macs, new_ifaces):
    new_macs = []
    for i in range(len(defined_macs)):
        ifname = "eth" + str(i)
        new_iface = new_ifaces.get(ifname)
        if new_iface:
            new_macs.append(generate_new_mac() if new_iface['mac'] == "auto" else new_iface['mac'])
        else:
            new_macs.append(generate_new_mac())
    return new_macs

def guestfs_open(imgpath):
    g = guestfs.GuestFS()
    g.set_autosync(1)
    g.add_drive_opts(imgpath, readonly=0)
    print_debug("==> guestfs launch(): %s" % imgpath)
    g.set_selinux(1)
    g.launch()
    print_debug("==> guestfs inspect_os()")
    roots = g.inspect_os()
    for root in roots:
        print "==> guestfs mount (root: %s)" % root
        print "  Product Name:", g.inspect_get_product_name(root)
        #print "  Product Variant:", g.inspect_get_product_variant(root)
        major = g.inspect_get_major_version(root)
        #print "  Major Version:", major
        minor = g.inspect_get_minor_version(root)
        #print "  Minor Version:", minor
        type = g.inspect_get_type(root)
        #print "  Type:", type
        distro = g.inspect_get_distro(root)
        #print "  Distro:", distro
        print "  Hostname:", g.inspect_get_hostname(root)
        #print "  Package Format:", g.inspect_get_package_format(root)
        #print "  Package Management:", g.inspect_get_package_management(root)
        mount_points = g.inspect_get_mountpoints(root)
        mount_points.sort(compare_pathlen)
        print "  Mount Points:", mount_points
        for mount_point, dev in mount_points:
            print_debug("    %s => %s" % (mount_point, dev))
            try:
                g.mount(dev, mount_point)
            except RuntimeError as msg:
                print_debug("%s (ignored)" % msg)
        g.aug_init("/", AUG_SAVE_BACKUP)

        if type != "linux":
            print "** %s is not supported." % type
            sys.exit(1)
        gflags['os'] = "%s-%s-%s-%s" % (type, distro, major, minor)
        print "  OS:", gflags['os']

        if g.exists("/sbin/load_policy"):
            g.sh("/sbin/load_policy")
            print "==> SElinux policy loaded"
    return g

def guestfs_close(g):
    g.aug_save()
    g.aug_close()
    g.sync()
    g.umount_all()

def guestfs_print_misc(g):
    print "==> guestfs_print_misc()"
    print " ", g.list_partitions()
    print " ", g.list_devices()
    print " ", g.list_filesystems()
    print " ", g.lvs()
    print " ", g.mounts()
    print " ", g.mountpoints()

def guestfs_write_file(g, path, content):
    print_debug("===> guestfs_write_file()")
    if g.exists(path):
        orig_path = path + ".adjuster_orig"
        print_debug("  file (%s) exists, creating backup as %s" % (path, orig_path))
        g.cp_a(path, orig_path)
    g.write(path, content)

def adjust_xml(xmlfile, **d):
    print "==> XML configuration of libvirt (%s)" % xmlfile
    print_debug("==> adjust_xml()")
    orig_xmlfile = xmlfile + ".orig"
    os.system("mv %s %s" % (xmlfile, orig_xmlfile))
    (newname, newext) = os.path.splitext(os.path.basename(xmlfile))
    newimage = os.path.abspath(d.get("image"))
    newuuid = d.get("uuid")
    newmacs = d.get("macs")
    xml = etree.parse(open(orig_xmlfile, 'r'), parser=etree.XMLParser())
    image = xml.xpath("/domain/devices/disk[@type='file' and @device='disk']/source/@file")[0]
    uuid = xml.xpath("/domain/uuid/text()")[0]
    macs = xml.xpath("/domain/devices/interface/mac/@address")
    print "  imgpath: %s => %s" % (image, newimage)
    print "  uuid: %s => %s" % (uuid, newuuid)
    print "  macs: %s => %s" % (macs, newmacs)
    xml.xpath("/domain/name")[0].text = newname
    xml.xpath("/domain/devices/disk[@type='file' and @device='disk']/source")[0].attrib["file"] = newimage
    xml.xpath("/domain/uuid")[0].text = newuuid
    for i, mac in enumerate(xml.xpath("/domain/devices/interface/mac")):
        if not newmacs[i]: continue
        mac.attrib["address"] = newmacs[i]
    xml.write(open(xmlfile, 'w'))

def linux_adjust_udev_rules(g, ifcfgs):
    print_debug("==> linux_adjust_udev_rules(): %s" % ifcfgs)
    udev_net_rule = "/etc/udev/rules.d/70-persistent-net.rules"
    print "==> udev rules (%s)" % udev_net_rule
    if not g.is_file(udev_net_rule):
        print_debug("linux_adjust_udev_rules(): %s is not file." % udev_net_rule)
        return
    orig_udev_net_rule = udev_net_rule + ".orig"
    g.mv(udev_net_rule, orig_udev_net_rule)
    sed_command = "sed"
    for ifname in sorted(ifcfgs.keys()):
        sed_command += " -e 's|\(ATTR{address}==\)\"%s\", |\\1\"%s\", |'" % (ifcfgs[ifname].mac, ifcfgs[ifname].newmac)
    sed_command += " %s > %s" % (orig_udev_net_rule, udev_net_rule)
    print_debug("  command: %s" % sed_command)
    g.sh(sed_command)

def rhel_adjust_resolvconf(g, nameservers, domains):
    print_debug("==> rhel_adjust_resolvconf()")
    path = "/etc/resolv.conf"
    print "==> resolver (%s)" % path
    augpath = "/files" + path
    if not g.exists(path):
        print "  %s not exists, creating..." % path
        g.sh("touch %s" % path)
    else:
        print "  %s exists, deleting existing entries..." % path
        g.aug_rm(augpath + "/nameserver")
        g.aug_rm(augpath + "/search")
    for ns in nameservers:
        if not g.aug_match(augpath + "/nameserver"):
            g.aug_set(augpath + "/nameserver", ns)
        else:
            g.aug_insert(augpath + "/nameserver[last()]", "nameserver", 0)
            g.aug_set(augpath + "/nameserver[last()]", ns)
    for dom in domains:
        if not g.aug_match(augpath + "/search"):
            g.aug_set(augpath + "/search/domain", dom)
        else:
            g.aug_insert(augpath + "/search/domain[last()]", "domain", 0)
            g.aug_set(augpath + "/search/domain[last()]", dom)
    g.aug_save()

def rhel_adjust_ifaces(g, defined_macs, new_ifaces, new_macs, nameservers, domains, primary, gateway):
    print_debug("==> rhel_adjust_ifaces()")
    for i, mac in enumerate(defined_macs):
        ifname = "eth" + str(i)
        print "==> %s" % ifname
        new_iface = new_ifaces.get(ifname)
        ifcfgs[ifname] = ifcfg_rhel(g, ifname)
        is_primary = (ifname == primary)
        if not new_iface:
            ifcfgs[ifname].prepare(mac=new_macs[i],
                                   uuid=generate_new_uuid())
        else:
            ifcfgs[ifname].prepare(bootproto  = "static" if new_iface['ipaddr'] != "dhcp" else "dhcp",
                                   mac        = new_macs[i],
                                   uuid       = generate_new_uuid(),
                                   ipaddr     = new_iface['ipaddr'] if new_iface['ipaddr'] != "dhcp" else None,
                                   netmask    = new_iface['netmask'] if new_iface['ipaddr'] != "dhcp" else None,
                                   primary    = is_primary,
                                   gateway    = gateway if is_primary else None,
                                   nameserver = nameservers if is_primary else None,
                                   domain     = domains if is_primary else None)
        ifcfgs[ifname].info()
        ifcfgs[ifname].commit_update()

def rhel_adjust_hostname(g, new_hostname):
    print_debug("==> rhel_adjust_hostname()")
    path = "/etc/sysconfig/network"
    print "==> hostname (%s)" % path
    augpath = "/files" + path + "/HOSTNAME"
    old_hostname = g.aug_get(augpath)
    print_debug("  %s => %s" % (old_hostname, new_hostname))
    g.aug_set(augpath, new_hostname)
    g.aug_save()

def rhel_adjust_grub(g):
    print_debug("==> rhel_adjust_grub()")
    path = "/boot/grub/menu.lst"
    print "==> grub configuration (%s)" % path
    augpath = "/files" + path
    default = g.aug_get(augpath + "/default")
    title = "/title[" + str(int(default) + 1) + "]"
    g.aug_get(augpath + title)
    if not g.aug_match(augpath + title + "/kernel/console"):
        g.aug_insert(augpath + title + "/kernel/root", "console", 0)
        g.aug_set(augpath + title + "/kernel/console", "ttyS0,115200n8")
        if g.aug_match(augpath + title + "/kernel/rhgb"): g.aug_rm(augpath + title + "/kernel/rhgb")
        if g.aug_match(augpath + title + "/kernel/quiet"): g.aug_rm(augpath + title + "/kernel/quiet")

    if not g.aug_match(augpath + "/serial"):
        g.aug_insert(augpath + "/hiddenmenu", "serial", 0)
        g.aug_set(augpath + "/serial/speed", "115200")
        g.aug_set(augpath + "/serial/unit", "0")
        g.aug_set(augpath + "/serial/word", "8")
        g.aug_set(augpath + "/serial/parity", "no")
        g.aug_set(augpath + "/serial/stop", "1")

    if not g.aug_match(augpath + "/terminal"):
        g.aug_insert(augpath + "/serial", "terminal", 0)
        g.aug_set(augpath + "/terminal/timeout", "5")
        g.aug_clear(augpath + "/terminal/serial")
        g.aug_clear(augpath + "/terminal/console")

    g.aug_save()
    
def rhel_adjust_upstart(g):
    print_debug("==> rhel_adjust_upstart()")
    conf = "/etc/init/start-ttys.conf"
    orig_conf = conf + ".orig"
    if g.egrep("\s+initctl\s+start\s+serial\s+DEV=[^\s]+\s+SPEED=[0-9]+", conf):
        print "  %s already has serial console configuration, skipping..." % conf
    else:
        command = "sed '/end script/i \	initctl start serial DEV=ttyS0 SPEED=115200'"
        g.mv(conf, orig_conf)
        g.sh(command + " %s > %s" % (orig_conf, conf))

def rhel_adjust_inittab(g):
    print_debug("==> rhel_adjust_inittab()")
    path = "/etc/inittab"
    print "==> inittab (%s)" % path
    g.aug_set("/files" + path + "/id/runlevels", "3")
    g.aug_save()

def rhel_adjust_misc(g):
    print "==> misc configuration"
    print_debug("==> rhel_adjust_misc()")
    path = "/etc/sysconfig/network"
    augpath = "/files" + path
    g.aug_set(augpath + "/NETWORKING", "yes")
    g.aug_set(augpath + "/NETWORKING_IPV6", "no")
    g.aug_save()

def get_all_macs_from_xml(xmlfile):
    xml = etree.parse(open(xmlfile, 'r'), parser=etree.XMLParser())
    return xml.xpath("/domain/devices/interface/mac/@address")

def ubuntu_adjust_ifaces(g, defined_macs, new_ifaces, new_macs, nameservers, domains, primary, gateway):
    print_debug("==> ubuntu_adjust_ifaces()")
    for i, mac in enumerate(defined_macs):
        ifname = "eth" + str(i)
        print "==> %s" % ifname
        new_iface = new_ifaces.get(ifname)
        ifcfgs[ifname] = ifcfg_ubuntu(g, ifname)
        is_primary = (ifname == primary)
        if not new_iface:
            continue
        ifcfgs[ifname].prepare(bootproto  = 'static' if new_iface['ipaddr'] != "dhcp" else 'dhcp',
                               ipaddr     = new_iface['ipaddr'] if new_iface['ipaddr'] != "dhcp" else None,
                               netmask    = new_iface['netmask'] if new_iface['ipaddr'] != "dhcp" else None,
                               primary    = is_primary,
                               gateway    = gateway if is_primary else None,
                               nameserver = nameservers if is_primary else None,
                               domain     = domains if is_primary else None)
        ifcfgs[ifname].info()
        ifcfgs[ifname].commit_update()

def ubuntu_adjust_hostname(g, new_hostname):
    print_debug("==> ubuntu_adjust_hostname()")
    conf = "/etc/hostname"
    print "==> hostname (%s)" % conf
    hostname = g.read_lines(conf)[0]
    print_debug("  %s => %s" % (hostname, new_hostname))
    guestfs_write_file(g, conf, new_hostname)
    
def ubuntu_adjust_grub(g):
    print_debug("==> ubuntu_adjust_grub()")
    conf = "/etc/default/grub"
    print "==> grub configuration (%s)" % conf
    orig_conf = conf + ".adjuster_orig"
    if g.egrep("GRUB_CMDLINE_LINUX.*tty", conf):
        print "  grub already has serial console configuration, skipping..."
    else:
        command = "sed"
        command += " -e 's/^GRUB_CMDLINE_LINUX=\"\\(.*\\)\"/GRUB_CMDLINE_LINUX=\"\\1 console=tty0 console=ttyS0,115200n8\"/'"
        command += " -e '/^GRUB_CMDLINE_LINUX=/i GRUB_TERMINAL=serial'"
        command += " -e '/^GRUB_CMDLINE_LINUX=/i GRUB_SERIAL_COMMAND=\"serial --speed=115200 --unit=0 --word=8 --parity=no --stop=1\"'"
        command += " %s > %s" % (orig_conf, conf)
        print_debug("  running sed...")
        print_debug("    command: %s" % command)
        g.mv(conf, orig_conf)
        g.sh(command)
        print_debug("  running update-grub...")
        g.sh("update-grub")

def ubuntu_adjust_upstart(g):
    print_debug("==> ubuntu_adjust_upstart()")
    conf = "/etc/init/ttyS0.conf"
    print "==> upstart configuration (%s)" % conf
    if g.exists(conf):
        print "  %s already exists, skipping..." % conf
    else:
        content = """start on stopped rc RUNLEVEL=[2345]
stop on runlevel [!2345]

respawn
exec /sbin/getty -L 115200 ttyS0 vt102
"""
        guestfs_write_file(g, conf, content)

def ubuntu_adjust_inittab(g): pass
def ubuntu_adjust_resolvconf(g, nameservers, domains): pass
def ubuntu_adjust_misc(g): pass

adjust_ops = {
    'linux-rhel-6': {
        'adjust_ifaces': rhel_adjust_ifaces,
        'adjust_udev_rules': linux_adjust_udev_rules,
        'adjust_hostname': rhel_adjust_hostname,
        'adjust_xml': adjust_xml,
        'adjust_grub': rhel_adjust_grub,
        'adjust_upstart': rhel_adjust_upstart,
        'adjust_inittab': rhel_adjust_inittab,
        'adjust_resolvconf': rhel_adjust_resolvconf,
        'adjust_misc': rhel_adjust_misc,
    },
    'linux-ubuntu-12': {
        'adjust_ifaces': ubuntu_adjust_ifaces,
        'adjust_udev_rules': linux_adjust_udev_rules,
        'adjust_hostname': ubuntu_adjust_hostname,
        'adjust_xml': adjust_xml,
        'adjust_grub': ubuntu_adjust_grub,
        'adjust_upstart': ubuntu_adjust_upstart,
        'adjust_inittab': ubuntu_adjust_inittab,
        'adjust_resolvconf': ubuntu_adjust_resolvconf,
        'adjust_misc': ubuntu_adjust_misc,
    },
}

def adjuster(os, opname):
    os_major = re.sub('-[^-]+$', '', os)
    print_debug("==> adjuster(): %s, %s, %s" % (opname, os, os_major))
    ops = adjust_ops.get(os_major)
    if not ops:
        print "OS not supported:", os
        sys.exit(1)
    op = ops.get(opname)
    if not op:
        print "Operation (%s) not defined, skipping..." % opname
    print_debug("  op: %s" % op)
    return op

class MyOptionParser(optparse.OptionParser):
    def format_epilog(self, formatter):
        return self.epilog

    usage = "%prog [--image IMAGEPATH] [--xml XMLPATH] [--interface INTERFACE_DESCRIPTION] [--primary INTERFACE] [--gateway IPADDRESS] [--nameserver NAMESERVERS] [--domain DOMAINS] [--hostname HOSTNAME] [--serial-console] [--debug]"
    epilog = """
Example:
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
"""

if __name__ == '__main__':
    #parser = optparse.OptionParser(usage=usage)
    parser = MyOptionParser(usage=MyOptionParser.usage, epilog=MyOptionParser.epilog)
    parser.add_option("--image", action="store", dest="imgpath", help="path of image file")
    parser.add_option("--xml", action="store", dest="xmlpath", help="path of XML file")
    parser.add_option("--interface", action="store", dest="interface", help="specifies interface infomation. the format of an interface is \"IFNAME/MAC/IPADDR/NETMASK\". use \"auto\" for MAC to be autogenerated. for DHCP, use \"dhcp\" in IPADDR. you can specify multiple interfaces separated by comma (',').")
    parser.add_option("--primary", action="store", dest="primary", help="specifies primary interface. settings of gateway, DNS, etc are written in this interface config file.")
    parser.add_option("--gateway", action="store", dest="gateway", help="default gateway")
    parser.add_option("--nameserver", action="store", dest="nameserver", help="DNS nameservers.")
    parser.add_option("--domain", action="store", dest="domain", help="DNS search domains.")
    parser.add_option("--hostname", action="store", dest="hostname", help="hostname")
    parser.add_option("--serial-console", action="store_true", dest="serial_console", help="serial console config for \"virsh console\".")
    parser.add_option("--debug", action="store_true", dest="debug")
    #group = OptionGroup(parser, "Example", "./kvm_image_adjuster.py --image=./test.img --xml=./test.xml --interface=eth0/auto/10.7.9.100/255.255.0.0,eth1/auto/dhcp/dhcp --primary=eth0 --gateway=10.0.0.1 --hostname=vm.example.com --nameserver=8.8.8.8,8.8.4.4 --domain=dept.example.com,example.com")
    #parser.add_option_group(group)
    (options, args) = parser.parse_args()
    gflags['debug'] = options.debug

    g = guestfs_open(options.imgpath)
    if options.debug: guestfs_print_misc(g)

    if options.interface:
        defined_macs = get_all_macs_from_xml(options.xmlpath)
        new_ifaces = parse_interface_option(options.interface)
        new_macs = generate_new_macs(defined_macs, new_ifaces)
        nameservers = options.nameserver.split(",")
        domains = options.domain.split(",")
        OS = gflags['os']

        print "=> adjust interfaces (img)"
        adjuster(OS, 'adjust_ifaces')(g, defined_macs, new_ifaces, new_macs,
                                      nameservers, domains, options.primary, options.gateway)
        adjuster(OS, 'adjust_udev_rules')(g, ifcfgs)
        adjuster(OS, 'adjust_hostname')(g, options.hostname)
        adjuster(OS, 'adjust_resolvconf')(g, nameservers, domains)
        print "=> adjust interfaces (xml)"
        adjuster(OS, 'adjust_xml')(options.xmlpath, image=options.imgpath, uuid=generate_new_uuid(), macs=new_macs)
        adjuster(OS, 'adjust_misc')(g)

    if options.serial_console:
        print "=> adjust for serial console"
        adjuster(OS, 'adjust_grub')(g)
        adjuster(OS, 'adjust_upstart')(g)
        adjuster(OS, 'adjust_inittab')(g)

    guestfs_close(g)
