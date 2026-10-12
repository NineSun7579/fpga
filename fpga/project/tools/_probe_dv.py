import re
p="host/detview/main.cpp"
b=open(p,"rb").read().decode("utf-8","replace").splitlines()
print("### lines:",len(b))
print("### usage/option/menu/printf-significant lines:")
for i,l in enumerate(b):
    s=l.strip()
    if re.search(r'argv|argc|usage|Usage|--\w|"-[a-zA-Z]|qDebug|printf|fprintf|std::cout|puts\(|help|option', s):
        print("%5d %s"%(i+1,s[:135]))
