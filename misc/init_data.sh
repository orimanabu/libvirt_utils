#!/bin/sh

if [ x"$#" != x"2" ]; then
	echo "$0 srcname dstname"
	exit 1
fi

srcname=$1; shift
dstname=$1; shift
#datadir=./test/data
datadir=.

for ext in img xml; do
	/bin/cp ${datadir}/${srcname}.${ext} ${datadir}/${dstname}.${ext}
done
