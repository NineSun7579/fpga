#!/bin/bash
cd /root/ov5640/detview
rm -f detview BUILD_RC
/usr/lib/qt5/bin/qmake
make -j4
echo "BUILD_RC=$?" > /root/ov5640/build_detview.result
ls -la detview >> /root/ov5640/build_detview.result 2>&1
