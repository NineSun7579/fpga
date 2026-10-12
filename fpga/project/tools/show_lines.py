import sys
path = r'source\top.v'
a, b = int(sys.argv[1]), int(sys.argv[2])
lines = open(path, 'rb').read().decode('gbk', 'replace').splitlines()
for i in range(a - 1, min(b, len(lines))):
    print(i + 1, lines[i])
