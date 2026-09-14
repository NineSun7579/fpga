# Minimal probe: does Sigmoid survive on the RK3568 device?
import numpy as np, onnx, sys
from onnx import helper, TensorProto
from rknn.api import RKNN

# tiny graph: input(1,3,8,8) -> Conv1x1(3->2) -> Sigmoid -> output
w = np.random.RandomState(0).randn(2,3,1,1).astype(np.float32)
b = np.zeros(2, np.float32)
nodes = [
    helper.make_node('Conv', ['input','W','B'], ['conv'], kernel_shape=[1,1], pads=[0,0,0,0], strides=[1,1]),
    helper.make_node('Sigmoid', ['conv'], ['output']),
]
graph = helper.make_graph(nodes, 'probe',
    [helper.make_tensor_value_info('input', TensorProto.FLOAT, [1,3,8,8])],
    [helper.make_tensor_value_info('output', TensorProto.FLOAT, [1,2,8,8])],
    [helper.make_tensor('W', TensorProto.FLOAT, [2,3,1,1], w.flatten()),
     helper.make_tensor('B', TensorProto.FLOAT, [2], b)])
m = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 13)])
m.ir_version = 8
onnx.save(m, '/mnt/c/Users/NineSun/Desktop/ov56401/control_model/probe.onnx')
print('probe.onnx saved')

rknn = RKNN(verbose=False)
rknn.config(mean_values=[[0,0,0]], std_values=[[255,255,255]], target_platform='rk3568')
assert rknn.load_onnx(model='/mnt/c/Users/NineSun/Desktop/ov56401/control_model/probe.onnx') == 0
assert rknn.build(do_quantization=True, dataset='/mnt/c/Users/NineSun/Desktop/ov56401/calib_png/dataset_linux.txt') == 0
assert rknn.export_rknn('/mnt/c/Users/NineSun/Desktop/ov56401/control_model/probe_sigmoid.rknn') == 0
print('PROBE CONVERT OK')
