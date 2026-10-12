echo __HELLO__
ffmpeg -y -loglevel error -i /tmp/c1a.ppm -vf "crop=80:48:20:140,scale=640:384:flags=neighbor" -q:v 2 /tmp/z1.jpg
ffmpeg -y -loglevel error -i /tmp/c2a.ppm -vf "crop=80:48:20:140,scale=640:384:flags=neighbor" -q:v 2 /tmp/z2.jpg
ffmpeg -y -loglevel error -i /tmp/c1a.ppm -vf "crop=160:96:320:200,scale=640:384:flags=neighbor" -q:v 2 /tmp/z3.jpg
ffmpeg -y -loglevel error -i /tmp/c2a.ppm -vf "crop=160:96:320:200,scale=640:384:flags=neighbor" -q:v 2 /tmp/z4.jpg
ls -l /tmp/z1.jpg /tmp/z2.jpg /tmp/z3.jpg /tmp/z4.jpg
echo __OK__
