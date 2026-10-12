#!/bin/bash
# 3568 PCIe驱动加载 + camview启动脚本

echo "=== 1. 加载PCIe驱动 ==="
lsmod | grep -i pcie
if [ $? -ne 0 ]; then
    echo "加载驱动模块..."
    # 根据实际驱动名称调整，可能是 pcie_fpga.ko 或其他
    insmod /path/to/pcie_driver.ko 2>&1 || echo "驱动加载失败或已加载"
fi

echo ""
echo "=== 2. 检查PCIe设备 ==="
lspci | grep -i xilinx -A2
lspci -d 10ee: -vvv | grep -E "Memory|Region|Control" | head -20

echo ""
echo "=== 3. 检查字符设备 ==="
ls -l /dev/xdma* 2>/dev/null || echo "未找到xdma设备节点"

echo ""
echo "=== 4. 启动camview ==="
cd /root || cd /home/firefly
if [ -f "./camview" ]; then
    ./camview &
    CAMVIEW_PID=$!
    echo "camview已启动 (PID: $CAMVIEW_PID)"
    echo "等待5秒后截图..."
    sleep 5
    
    echo ""
    echo "=== 5. 截图 ==="
    # 方式1: scrot (如果已安装)
    if command -v scrot &>/dev/null; then
        scrot /tmp/camview_6ch.png
        echo "截图已保存: /tmp/camview_6ch.png"
    # 方式2: fbgrab (framebuffer截图)
    elif command -v fbgrab &>/dev/null; then
        fbgrab /tmp/camview_6ch.png
        echo "截图已保存: /tmp/camview_6ch.png"
    # 方式3: 直接读framebuffer
    else
        echo "未找到截图工具，尝试直接读取framebuffer..."
        cat /dev/fb0 > /tmp/fb0.raw
        echo "framebuffer已保存: /tmp/fb0.raw (需要手动转换)"
    fi
    
    echo ""
    echo "=== 6. 检查camview进程状态 ==="
    ps aux | grep camview | grep -v grep
    
    echo ""
    echo "完成！如需停止camview: kill $CAMVIEW_PID"
else
    echo "错误: 未找到camview可执行文件"
    echo "当前目录: $(pwd)"
    ls -lh camview 2>&1
fi
