// qshot.cpp - tiny on-board screenshot tool: grab screen, scale, save PNG
// Build: qmake qshot.pro && make ; Run: DISPLAY=:0 ./qshot /tmp/qshot.png 640
#include <QApplication>
#include <QScreen>
#include <QPixmap>
#include <QFile>
#include <cstdio>
int main(int argc, char **argv) {
    QApplication app(argc, argv);
    const char *out = argc > 1 ? argv[1] : "/tmp/qshot.png";
    int w = argc > 2 ? atoi(argv[2]) : 640;
    QScreen *sc = QApplication::primaryScreen();
    if (!sc) { fprintf(stderr, "no screen\n"); return 1; }
    QPixmap pm = sc->grabWindow(0);
    int h = pm.height() * w / pm.width();
    pm.scaled(w, h, Qt::KeepAspectRatio, Qt::SmoothTransformation)
      .save(out, "PNG");
    printf("OK %dx%d %ld\n", w, h, (long)QFile(out).size());
    return 0;
}
