"""Recompute mailbox connectivity from the actual routed graph, fail closed."""

def descendants(node, tag):
    if isinstance(node, list):
        if node and node[0] == tag:
            yield node
        for child in node:
            yield from descendants(child, tag)


def parameter(primitive, name):
    values = {entry[1]: entry for entry in primitive['default_parameters']}
    for entry in primitive['parameters']:
        for item in descendants(entry, 'PARAMETER'):
            values[item[1]] = item
    bits = list(descendants(values[name], 'B'))
    if len(bits) != 1:
        raise ValueError('Missing/unrecognized CLKROUTE initialization: ' + name)
    return int(bits[0][2].strip('"'), 2)


def identity_connection(graph, launch_q, capture_d):
    primitives, pins = graph['primitives'], graph['pin_net']
    if launch_q not in pins or capture_d not in pins:
        raise ValueError('Missing routed mailbox Q or D')
    target_net = pins[launch_q]
    net, seen, steps = pins[capture_d], set(), []
    while True:
        if net in seen:
            raise ValueError('Cycle in routed mailbox connection')
        seen.add(net)
        drivers = []
        for pin in graph['netpins'][net]:
            cell, port = pin.rsplit('/', 1)
            if primitives[cell]['ports'][port]['direction'] == 'OUTPUT':
                drivers.append(pin)
        if len(drivers) != 1:
            raise ValueError('Mailbox net lacks a unique physical driver')
        driver = drivers[0]
        if net == target_net:
            if driver != launch_q:
                raise ValueError('Launch net driven by a different physical output')
            return {'direct': not steps, 'identity_buffers': steps}
        cell, port = driver.rsplit('/', 1)
        primitive = primitives[cell]
        if primitive['type'] != 'gopCLKROUTE' or port != 'CR':
            raise ValueError('Unsupported mailbox intermediate driver: ' + driver)
        expected = [0, (1 << 64) - 1, 0, (1 << 64) - 1]
        if [parameter(primitive, 'INIT' + key) for key in 'ABCD'] != expected:
            raise ValueError('Non-identity CLKROUTE in mailbox data path')
        steps.append({'output': driver, 'input': cell + '/M'})
        net = pins[cell + '/M']
